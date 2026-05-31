from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry
from mcp_toolkit.core.security import resolve_workspace_path


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def workspace_stats(
        path: Annotated[
            str,
            Field(title="路径", description="MCP_WORKSPACE 内要统计的文件或目录路径。"),
        ] = ".",
    ) -> dict[str, int | str]:
        """统计工作区路径下的文件数、目录数和总字节数。"""
        root = resolve_workspace_path(settings.workspace, path)
        if not root.exists():
            raise FileNotFoundError(f"路径不存在: {root}")

        files = 0
        directories = 0
        total_bytes = 0
        iterator = root.rglob("*") if root.is_dir() else [root]

        for item in iterator:
            if item.is_dir():
                directories += 1
            elif item.is_file():
                files += 1
                total_bytes += item.stat().st_size

        return {
            "path": str(Path(path)),
            "files": files,
            "directories": directories,
            "total_bytes": total_bytes,
        }
