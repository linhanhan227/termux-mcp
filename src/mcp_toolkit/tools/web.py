from __future__ import annotations

import base64
import binascii
import html
import re
import urllib.parse
from typing import Annotated, Literal

import httpx
from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


Provider = Literal["auto", "tavily", "bing"]

BING_SEARCH_URL = "https://www.bing.com/search"
SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
PUBLIC_SEARCH_PAGE_SIZE = 10
PUBLIC_SEARCH_MAX_RESULTS = 50
PUBLIC_SEARCH_MAX_PAGES = 10
TAVILY_MAX_RESULTS = 20


def _parse_html_attrs(raw_attrs: str) -> dict[str, str]:
    pattern = re.compile(
        r"""([a-zA-Z_:][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""",
        re.DOTALL,
    )
    return {
        match.group(1).lower(): html.unescape(
            next(value for value in match.groups()[1:] if value is not None)
        )
        for match in pattern.finditer(raw_attrs)
    }


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


def _decode_bing_url(url: str) -> str:
    decoded = html.unescape(url)
    parsed = urllib.parse.urlparse(decoded)
    if parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/a"):
        target = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
        if target:
            if target.startswith("a1"):
                target = target[2:]
            padding = "=" * (-len(target) % 4)
            try:
                decoded_target = base64.urlsafe_b64decode(target + padding).decode("utf-8")
                return urllib.parse.unquote(decoded_target)
            except (binascii.Error, ValueError, UnicodeDecodeError):
                return urllib.parse.unquote(target)
    return decoded


def _parse_bing_results(body: str, max_results: int) -> list[dict[str, object]]:
    block_pattern = re.compile(
        r'<li[^>]+class="[^"]*\bb_algo\b[^"]*"[^>]*>(.*?)(?=<li[^>]+class="[^"]*\bb_algo\b|</ol>)',
        re.IGNORECASE | re.DOTALL,
    )
    link_pattern = re.compile(
        r'<h2[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    for block in block_pattern.finditer(body):
        link = link_pattern.search(block.group(1))
        if not link:
            continue
        url = _decode_bing_url(link.group(1))
        title = _strip_html(link.group(2))
        snippet = snippet_pattern.search(block.group(1))
        content = _strip_html(snippet.group(1)) if snippet else ""
        if not url or not title or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "content": content})
        if len(results) >= max_results:
            break
    return results


def _parse_bing_next_params(body: str) -> dict[str, str] | None:
    link_pattern = re.compile(r"<a\b([^>]*)>", re.IGNORECASE | re.DOTALL)
    for link in link_pattern.finditer(body):
        attrs = _parse_html_attrs(link.group(1))
        classes = attrs.get("class", "").split()
        label = attrs.get("aria-label", "") + attrs.get("title", "")
        if "sb_pagN" not in classes and "下一页" not in label and "Next" not in label:
            continue

        href = attrs.get("href")
        if not href:
            continue
        query = urllib.parse.urlparse(href).query
        params = urllib.parse.parse_qs(query)
        return {name: values[-1] for name, values in params.items() if values}
    return None


def _append_unique_results(
    results: list[dict[str, object]],
    seen_urls: set[str],
    candidates: list[dict[str, object]],
    limit: int,
) -> int:
    added = 0
    for item in candidates:
        url = item.get("url")
        if not isinstance(url, str) or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(item)
        added += 1
        if len(results) >= limit:
            break
    return added


def _request_timeout(seconds: float) -> httpx.Timeout:
    timeout = max(seconds, 0.1)
    return httpx.Timeout(timeout, connect=min(timeout, 5.0))


def _bing_base_params(query: str) -> dict[str, str]:
    return {"q": query, "mkt": "zh-CN", "cc": "CN", "setlang": "zh-Hans"}


def _search_headers() -> dict[str, str]:
    return {
        "User-Agent": SEARCH_USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def _http_status_error(provider: str, exc: httpx.HTTPStatusError) -> RuntimeError:
    body = exc.response.text[:1000]
    return RuntimeError(f"{provider} 搜索失败，HTTP {exc.response.status_code}: {body}")


async def _search_tavily(query: str, limit: int, settings: Settings) -> dict[str, object]:
    tavily_limit = min(limit, TAVILY_MAX_RESULTS)
    payload = {
        "query": query,
        "max_results": tavily_limit,
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
        async with httpx.AsyncClient(timeout=_request_timeout(settings.request_timeout)) as client:
            response = await client.post(settings.tavily_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise _http_status_error("Tavily", exc) from exc
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


async def _search_bing(query: str, limit: int, settings: Settings) -> dict[str, object]:
    results: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    params = _bing_base_params(query)
    if limit > PUBLIC_SEARCH_PAGE_SIZE:
        params["count"] = str(PUBLIC_SEARCH_PAGE_SIZE)
    requested_pages: set[tuple[tuple[str, str], ...]] = set()
    try:
        async with httpx.AsyncClient(
            timeout=_request_timeout(settings.request_timeout),
            follow_redirects=True,
        ) as client:
            for page_index in range(PUBLIC_SEARCH_MAX_PAGES):
                page_key = tuple(sorted(params.items()))
                if page_key in requested_pages:
                    break
                requested_pages.add(page_key)

                response = await client.get(
                    BING_SEARCH_URL,
                    params=params,
                    headers=_search_headers(),
                )
                response.raise_for_status()
                body = response.text
                page_results = _parse_bing_results(body, PUBLIC_SEARCH_PAGE_SIZE)
                added = _append_unique_results(results, seen_urls, page_results, limit)
                if len(results) >= limit or len(page_results) < PUBLIC_SEARCH_PAGE_SIZE:
                    break

                fallback_offset = (page_index + 1) * PUBLIC_SEARCH_PAGE_SIZE + 1
                fallback_params = {
                    **_bing_base_params(query),
                    "count": str(PUBLIC_SEARCH_PAGE_SIZE),
                    "first": str(fallback_offset),
                }
                if added == 0:
                    params = fallback_params
                    continue

                next_params = _parse_bing_next_params(body)
                if next_params:
                    for name, value in _bing_base_params(query).items():
                        next_params.setdefault(name, value)
                    params = next_params
                else:
                    params = fallback_params
    except httpx.HTTPStatusError as exc:
        raise _http_status_error("Bing", exc) from exc
    except httpx.HTTPError as exc:
        raise ConnectionError(f"Bing 搜索失败: {exc}") from exc

    return {
        "provider": "bing",
        "query": query,
        "answer": "",
        "results": results,
    }


def register_web_search_tool(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    async def web_search(
        query: Annotated[str, Field(title="搜索词", description="要联网搜索的关键词或问题。")],
        max_results: Annotated[
            int,
            Field(
                title="最大结果数",
                description="最多返回的搜索结果数量，实际限制在 1 到 50；Bing 搜索会自动翻页。",
            ),
        ] = 5,
        provider: Annotated[
            Provider,
            Field(
                title="搜索提供方",
                description=(
                    "auto 优先使用 Tavily；未配置 Tavily Key 时使用 Bing；"
                    "也可显式选择 tavily 或 bing。"
                ),
            ),
        ] = "auto",
    ) -> dict[str, object]:
        """联网搜索公开网页，返回标题、URL 和摘要。"""
        limit = max(1, min(max_results, PUBLIC_SEARCH_MAX_RESULTS))
        if provider == "auto":
            if settings.tavily_api_key:
                try:
                    return await _search_tavily(query, limit, settings)
                except ConnectionError:
                    return await _search_bing(query, limit, settings)
            return await _search_bing(query, limit, settings)

        if provider == "tavily":
            if settings.tavily_api_key:
                return await _search_tavily(query, limit, settings)
            raise ValueError("显式选择 provider=tavily 时必须设置 TAVILY_API_KEY。")

        if provider == "bing":
            return await _search_bing(query, limit, settings)

        raise ValueError("provider 只支持 auto、tavily、bing。")


register_web_tools = register_web_search_tool
