from __future__ import annotations

from pathlib import Path


def resolve_workspace_path(workspace: Path, user_path: str | Path) -> Path:
    base = workspace.expanduser().resolve()
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"路径位于 MCP_WORKSPACE 之外: {resolved}") from exc

    return resolved


def display_path(workspace: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return str(path)
