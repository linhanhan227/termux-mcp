from __future__ import annotations

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry

from .agent import register_agent_tool
from .files import register_file_operation_tool
from .web import register_web_search_tool


def register_builtin_tools(registry: ToolRegistry, settings: Settings) -> None:
    register_web_search_tool(registry, settings)
    register_file_operation_tool(registry, settings)
    register_agent_tool(registry, settings)
