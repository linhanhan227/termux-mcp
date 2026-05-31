from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def add(
        a: Annotated[float, Field(title="数字 A", description="第一个加数。")],
        b: Annotated[float, Field(title="数字 B", description="第二个加数。")],
    ) -> float:
        """计算两个数字之和。"""
        return a + b

    @registry.tool()
    def average(
        values: Annotated[list[float], Field(title="数字列表", description="用于计算数量、总和和平均值的数字列表。")],
    ) -> dict[str, float | int]:
        """计算数字列表的数量、总和和平均值。"""
        if not values:
            raise ValueError("values 不能为空")
        total = sum(values)
        return {
            "count": len(values),
            "sum": total,
            "average": total / len(values),
        }
