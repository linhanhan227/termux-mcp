# MCP Toolkit Tool Development

This project keeps tool implementation separate from the MCP server startup code.
Add tools by creating a Python module with a `register(registry, settings)` function.

The server is installed and run with the system Python. On Termux this is usually
`/data/data/com.termux/files/usr/bin/python`; avoid relying on a project-local
virtual environment or `PYTHONPATH=src` when documenting plugin setup.

## Minimal plugin

```python
from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b
```

Enable it with:

```sh
export MCP_TOOLKIT_PLUGINS=examples.custom_tools
mcp-toolkit
```

## Tool rules

- Use type annotations for every parameter and return value.
- Write a concise docstring; MCP clients use it as tool description.
- Keep side effects explicit. Read-only tools should be the default.
- Use `settings.workspace` plus `resolve_workspace_path` for filesystem tools.
- Put credentials in environment variables instead of source code.

## Built-in tools

The built-in surface is intentionally small:

- `web_search`: public web search through Tavily when `TAVILY_API_KEY` is configured, otherwise DuckDuckGo HTML search.
- `file_operation`: list, inspect, read, write, append, replace, mkdir, copy, move, delete, find, and grep paths under `MCP_WORKSPACE`.
- `agent`: lightweight task-state tracking for goal, steps, notes, and completion status.

Add specialized behavior as plugins unless it clearly belongs in one of these three built-in entry points.
