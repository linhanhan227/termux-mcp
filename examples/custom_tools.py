from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def echo(
        text: Annotated[str, Field(title="文本", description="要原样返回的文本。")],
    ) -> dict[str, str]:
        """原样返回输入文本，用于演示最小自定义 MCP 工具。"""
        return {
            "text": text,
            "workspace": str(settings.workspace),
        }
