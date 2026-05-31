from __future__ import annotations

import fnmatch
import hashlib
import re
import shutil
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry
from mcp_toolkit.core.security import display_path, resolve_workspace_path


FileAction = Literal[
    "list",
    "info",
    "read",
    "read_lines",
    "write",
    "append",
    "replace",
    "mkdir",
    "copy",
    "move",
    "delete",
    "find",
    "grep",
]

_SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "venv"}


def _ensure_write_enabled(settings: Settings) -> None:
    if not settings.allow_write:
        raise PermissionError("file_operation 的写入、移动、复制、删除操作已禁用。设置 MCP_ALLOW_WRITE=true 后启用。")


def _ensure_readable_file(path: Path, settings: Settings) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"不是文件: {path}")
    size = path.stat().st_size
    if size > settings.max_file_bytes:
        raise ValueError(f"文件过大: {size} 字节 > MCP_MAX_FILE_BYTES")


def _ensure_not_workspace_root(path: Path, settings: Settings, operation: str) -> None:
    if path.resolve() == settings.workspace.resolve():
        raise PermissionError(f"拒绝{operation} MCP_WORKSPACE 根目录")


def _required(value: str | None, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} 参数不能为空")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(root: Path, pattern: str) -> list[Path]:
    if root.is_file():
        return [root] if fnmatch.fnmatch(root.name, pattern) or pattern in {"", "*", "**/*"} else []

    files: list[Path] = []
    for item in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in item.parts):
            continue
        if item.is_file() and fnmatch.fnmatch(str(item.relative_to(root)), pattern):
            files.append(item)
    return files


def register_file_operation_tool(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def file_operation(
        action: Annotated[
            FileAction,
            Field(
                title="操作",
                description="文件操作类型：list/info/read/read_lines/write/append/replace/mkdir/copy/move/delete/find/grep。",
            ),
        ],
        path: Annotated[str, Field(title="路径", description="MCP_WORKSPACE 内的文件或目录路径。")] = ".",
        content: Annotated[
            str | None,
            Field(title="内容", description="write/append 操作写入的文本内容；replace 操作中表示查找文本。"),
        ] = None,
        destination: Annotated[
            str | None,
            Field(title="目标路径", description="copy/move 操作的目标路径，必须在 MCP_WORKSPACE 内。"),
        ] = None,
        replacement: Annotated[
            str | None,
            Field(title="替换文本", description="replace 操作使用的替换文本。"),
        ] = None,
        query: Annotated[
            str | None,
            Field(title="查询", description="grep 操作使用的正则表达式；也可作为 replace 的查找文本。"),
        ] = None,
        pattern: Annotated[str, Field(title="匹配模式", description="find/grep 使用的 glob 文件匹配模式。")] = "*",
        recursive: Annotated[bool, Field(title="递归", description="list/delete 操作是否递归处理目录。")] = False,
        overwrite: Annotated[bool, Field(title="覆盖", description="write/copy/move 目标已存在时是否覆盖。")] = False,
        include_hash: Annotated[bool, Field(title="计算 SHA-256", description="info 操作是否计算普通文件 SHA-256。")] = False,
        regex: Annotated[bool, Field(title="正则", description="replace 操作是否按正则表达式查找。")] = False,
        case_sensitive: Annotated[bool, Field(title="区分大小写", description="grep 操作是否区分大小写。")] = False,
        start_line: Annotated[int, Field(title="起始行", description="read_lines 从第几行开始读取，行号从 1 开始。")] = 1,
        max_lines: Annotated[int, Field(title="最大行数", description="read_lines 最多返回行数，实际限制在 1 到 1000。")] = 200,
        max_chars: Annotated[int, Field(title="最大字符数", description="read 最多返回字符数，实际限制在 1 到 MCP_MAX_FILE_BYTES。")] = 20000,
        max_entries: Annotated[int, Field(title="最大条目数", description="list/find/grep 最多返回条目数，实际限制在 1 到 1000。")] = 200,
        count: Annotated[int, Field(title="替换次数", description="replace 最多替换次数；0 表示全部替换。")] = 0,
    ) -> dict[str, object]:
        """在 MCP_WORKSPACE 内执行文件操作；写入、复制、移动、删除需要 MCP_ALLOW_WRITE=true。"""
        target = resolve_workspace_path(settings.workspace, path)
        entry_limit = max(1, min(max_entries, 1000))

        if action == "list":
            if not target.exists():
                raise FileNotFoundError(f"路径不存在: {target}")
            if not target.is_dir():
                raise NotADirectoryError(f"不是目录: {target}")
            entries = []
            iterator = target.rglob("*") if recursive else target.iterdir()
            for item in sorted(iterator):
                if any(part in _SKIP_DIRS for part in item.parts):
                    continue
                stat = item.stat()
                entries.append(
                    {
                        "path": display_path(settings.workspace, item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": int(stat.st_mtime),
                    }
                )
                if len(entries) >= entry_limit:
                    break
            return {"operation": action, "path": display_path(settings.workspace, target), "entries": entries}

        if action == "info":
            if not target.exists():
                raise FileNotFoundError(f"路径不存在: {target}")
            stat = target.stat()
            result: dict[str, object] = {
                "operation": action,
                "path": display_path(settings.workspace, target),
                "type": "directory" if target.is_dir() else "file",
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
                "is_symlink": target.is_symlink(),
            }
            if include_hash:
                _ensure_readable_file(target, settings)
                result["sha256"] = _sha256_file(target)
            return result

        if action == "read":
            _ensure_readable_file(target, settings)
            limit = max(1, min(max_chars, settings.max_file_bytes))
            with target.open("r", encoding="utf-8", errors="replace") as file:
                text = file.read(limit + 1)
            return {
                "operation": action,
                "path": display_path(settings.workspace, target),
                "content": text[:limit],
                "truncated": len(text) > limit,
                "size": target.stat().st_size,
            }

        if action == "read_lines":
            _ensure_readable_file(target, settings)
            first = max(1, start_line)
            line_limit = max(1, min(max_lines, 1000))
            lines: list[dict[str, object]] = []
            with target.open("r", encoding="utf-8", errors="replace") as file:
                for line_number, line in enumerate(file, start=1):
                    if line_number < first:
                        continue
                    if len(lines) >= line_limit:
                        break
                    lines.append({"line": line_number, "text": line.rstrip("\n")})
            return {"operation": action, "path": display_path(settings.workspace, target), "lines": lines}

        if action == "write":
            _ensure_write_enabled(settings)
            if target.exists() and not overwrite:
                raise FileExistsError("目标文件已存在；传入 overwrite=true 可替换它")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_required(content, "content"), encoding="utf-8")
            return {"operation": action, "path": display_path(settings.workspace, target), "bytes": target.stat().st_size}

        if action == "append":
            _ensure_write_enabled(settings)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as file:
                file.write(_required(content, "content"))
            return {"operation": action, "path": display_path(settings.workspace, target), "bytes": target.stat().st_size}

        if action == "replace":
            _ensure_write_enabled(settings)
            _ensure_readable_file(target, settings)
            search = query if query is not None else _required(content, "content 或 query")
            if not regex and search == "":
                raise ValueError("普通文本替换时查找文本不能为空")
            replace_with = _required(replacement, "replacement")
            original = target.read_text(encoding="utf-8", errors="replace")
            safe_count = max(0, count)
            if regex:
                updated, replacements = re.subn(search, replace_with, original, count=safe_count)
            else:
                replacements = original.count(search) if safe_count == 0 else min(original.count(search), safe_count)
                updated = original.replace(search, replace_with) if safe_count == 0 else original.replace(search, replace_with, safe_count)
            target.write_text(updated, encoding="utf-8")
            return {
                "operation": action,
                "path": display_path(settings.workspace, target),
                "replacements": replacements,
                "bytes": target.stat().st_size,
            }

        if action == "mkdir":
            _ensure_write_enabled(settings)
            if target.exists() and not target.is_dir():
                raise FileExistsError(f"路径已存在且不是目录: {target}")
            target.mkdir(parents=True, exist_ok=True)
            return {"operation": action, "path": display_path(settings.workspace, target), "created_or_existing": True}

        if action == "copy":
            _ensure_write_enabled(settings)
            dest = resolve_workspace_path(settings.workspace, _required(destination, "destination"))
            if not target.exists():
                raise FileNotFoundError(f"源路径不存在: {target}")
            _ensure_not_workspace_root(target, settings, "复制")
            if target.resolve() == dest.resolve():
                raise ValueError("源路径和目标路径不能相同")
            if target.is_dir() and dest.resolve().is_relative_to(target.resolve()):
                raise ValueError("不能把目录复制到自身内部")
            if dest.exists():
                if not overwrite:
                    raise FileExistsError("目标路径已存在；传入 overwrite=true 可替换它")
                _ensure_not_workspace_root(dest, settings, "覆盖")
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.copytree(target, dest)
                copied_type = "directory"
            else:
                shutil.copy2(target, dest)
                copied_type = "file"
            return {
                "operation": action,
                "source": display_path(settings.workspace, target),
                "destination": display_path(settings.workspace, dest),
                "type": copied_type,
            }

        if action == "move":
            _ensure_write_enabled(settings)
            dest = resolve_workspace_path(settings.workspace, _required(destination, "destination"))
            if not target.exists():
                raise FileNotFoundError(f"源路径不存在: {target}")
            _ensure_not_workspace_root(target, settings, "移动")
            if target.resolve() == dest.resolve():
                raise ValueError("源路径和目标路径不能相同")
            if target.is_dir() and dest.resolve().is_relative_to(target.resolve()):
                raise ValueError("不能把目录移动到自身内部")
            if dest.exists():
                if not overwrite:
                    raise FileExistsError("目标路径已存在；传入 overwrite=true 可替换它")
                _ensure_not_workspace_root(dest, settings, "覆盖")
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(dest))
            return {
                "operation": action,
                "source": display_path(settings.workspace, target),
                "destination": display_path(settings.workspace, dest),
                "moved": True,
            }

        if action == "delete":
            _ensure_write_enabled(settings)
            if not target.exists():
                raise FileNotFoundError(f"路径不存在: {target}")
            _ensure_not_workspace_root(target, settings, "删除")
            if target.is_dir():
                if not recursive:
                    raise IsADirectoryError("目标是目录；传入 recursive=true 才会递归删除")
                shutil.rmtree(target)
                deleted_type = "directory"
            else:
                target.unlink()
                deleted_type = "file"
            return {"operation": action, "path": display_path(settings.workspace, target), "type": deleted_type, "deleted": True}

        if action == "find":
            if not target.exists():
                raise FileNotFoundError(f"路径不存在: {target}")
            matches = [display_path(settings.workspace, item) for item in _iter_files(target, pattern)[:entry_limit]]
            return {"operation": action, "path": display_path(settings.workspace, target), "pattern": pattern, "matches": matches}

        if action == "grep":
            if not target.exists():
                raise FileNotFoundError(f"路径不存在: {target}")
            flags = 0 if case_sensitive else re.IGNORECASE
            regex_obj = re.compile(_required(query, "query"), flags)
            matches = []
            for file_path in _iter_files(target, pattern):
                if len(matches) >= entry_limit:
                    break
                if file_path.stat().st_size > settings.max_file_bytes:
                    continue
                with file_path.open("r", encoding="utf-8", errors="ignore") as file:
                    for line_number, line in enumerate(file, start=1):
                        if regex_obj.search(line):
                            matches.append(
                                {
                                    "path": display_path(settings.workspace, file_path),
                                    "line": line_number,
                                    "text": line.rstrip("\n"),
                                }
                            )
                            if len(matches) >= entry_limit:
                                break
            return {"operation": action, "path": display_path(settings.workspace, target), "pattern": pattern, "matches": matches}

        raise ValueError(f"未知文件操作: {action}")


register_file_tools = register_file_operation_tool
