from __future__ import annotations

import html
import re
import urllib.parse
from typing import Annotated, Literal

import httpx
from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


Provider = Literal["auto", "tavily", "duckduckgo"]


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


def _decode_duckduckgo_url(url: str) -> str:
    decoded = html.unescape(url)
    if decoded.startswith("//"):
        decoded = "https:" + decoded
    parsed = urllib.parse.urlparse(decoded)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return target
    return decoded


def _parse_duckduckgo_results(body: str, max_results: int) -> list[dict[str, object]]:
    pattern = re.compile(
        r'<a[^>]+class="[^"]*\bresult__a\b[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    for match in pattern.finditer(body):
        url = _decode_duckduckgo_url(match.group(1))
        title = _strip_html(match.group(2))
        if not url or not title or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "content": ""})
        if len(results) >= max_results:
            break
    return results


def register_web_search_tool(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    async def web_search(
        query: Annotated[str, Field(title="搜索词", description="要联网搜索的关键词或问题。")],
        max_results: Annotated[
            int,
            Field(title="最大结果数", description="最多返回的搜索结果数量，实际限制在 1 到 10。"),
        ] = 5,
        provider: Annotated[
            Provider,
            Field(title="搜索提供方", description="auto 优先使用 Tavily；未配置 Tavily Key 时使用 DuckDuckGo HTML 搜索。"),
        ] = "auto",
    ) -> dict[str, object]:
        """联网搜索公开网页，返回标题、URL 和摘要。"""
        limit = max(1, min(max_results, 10))
        selected_provider = provider
        if selected_provider == "auto" or (selected_provider == "tavily" and not settings.tavily_api_key):
            selected_provider = "tavily" if settings.tavily_api_key else "duckduckgo"

        if selected_provider == "tavily":
            payload = {
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
                "include_answer": True,
                "include_raw_content": False,
                "include_images": False,
            }
            headers = {
                "Authorization": f"Bearer {settings.tavily_api_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                    response = await client.post(settings.tavily_api_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:1000]
                raise RuntimeError(f"Tavily 搜索失败，HTTP {exc.response.status_code}: {body}") from exc
            except httpx.HTTPError as exc:
                raise ConnectionError(f"Tavily 搜索失败: {exc}") from exc

            return {
                "provider": "tavily",
                "query": query,
                "answer": data.get("answer", ""),
                "results": [
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score"),
                    }
                    for item in data.get("results", [])[:limit]
                ],
            }

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=True) as client:
                response = await client.get(
                    "https://duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "mcp-toolkit-server/0.1"},
                )
                response.raise_for_status()
                body = response.text
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000]
            raise RuntimeError(f"DuckDuckGo 搜索失败，HTTP {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            raise ConnectionError(f"DuckDuckGo 搜索失败: {exc}") from exc

        return {
            "provider": "duckduckgo",
            "query": query,
            "answer": "",
            "results": _parse_duckduckgo_results(body, limit),
        }


register_web_tools = register_web_search_tool
