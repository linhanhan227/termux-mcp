from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from .config import Settings


class ToolRegistrar(Protocol):
    def __call__(self, registry: "ToolRegistry", settings: Settings) -> None: ...


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    handler: Callable[..., Any]
    description: str | None


class ToolRegistry:
    """让工具定义与 FastMCP 启动逻辑保持解耦的小适配器。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            if tool_name in self._tools:
                raise ValueError(f"MCP 工具名重复: {tool_name}")

            tool_description = description or inspect.getdoc(func)
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                handler=func,
                description=tool_description,
            )
            return func

        return decorator

    @property
    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())

    def register_to(self, server: FastMCP) -> None:
        for spec in self.tools:
            server.tool(name=spec.name, description=spec.description)(spec.handler)


def load_plugin_modules(
    registry: ToolRegistry,
    settings: Settings,
    modules: Iterable[str],
) -> None:
    for module_name in modules:
        module = importlib.import_module(module_name)
        register = getattr(module, "register", None)
        if not callable(register):
            raise TypeError(f"插件 {module_name!r} 必须暴露 register(registry, settings)")
        register(registry, settings)
