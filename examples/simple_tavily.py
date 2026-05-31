from __future__ import annotations

from typing import Annotated

import httpx
from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    async def simple_web_search(
        query: Annotated[str, Field(title="搜索词", description="要提交给 Tavily 的搜索查询。")],
        max_results: Annotated[
            int,
            Field(title="最大结果数", description="最多返回的搜索结果数量，实际限制在 1 到 10。"),
        ] = 3,
    ) -> dict[str, object]:
        """搜索网页并返回简化后的 Tavily 结果。"""
        if not settings.tavily_api_key:
            raise PermissionError("需要设置 TAVILY_API_KEY")

        payload = {
            "query": query,
            "max_results": max(1, min(max_results, 10)),
            "search_depth": "basic",
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.tavily_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(settings.tavily_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return {
            "query": query,
            "answer": data.get("answer"),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "score": item.get("score"),
                }
                for item in data.get("results", [])
            ],
        }
