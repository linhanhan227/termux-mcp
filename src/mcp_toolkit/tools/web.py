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


Provider = Literal["auto", "tavily", "duckduckgo", "bing"]

DUCKDUCKGO_SEARCH_URLS = (
    "https://duckduckgo.com/html/",
    "https://html.duckduckgo.com/html/",
)
BING_SEARCH_URL = "https://www.bing.com/search"
SEARCH_USER_AGENT = "Mozilla/5.0 (compatible; mcp-toolkit-server/0.1)"


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


def _request_timeout(seconds: float) -> httpx.Timeout:
    timeout = max(seconds, 0.1)
    return httpx.Timeout(timeout, connect=min(timeout, 5.0))


def _provider_failure(provider: str, errors: list[str]) -> ConnectionError:
    details = "；".join(errors)
    return ConnectionError(
        f"{provider} 搜索失败: {details}。如果当前网络不能直连该搜索服务，"
        "请设置 TAVILY_API_KEY 使用 Tavily，或配置 HTTPS_PROXY/HTTP_PROXY 后重试。"
    )


def _http_status_error(provider: str, exc: httpx.HTTPStatusError) -> RuntimeError:
    body = exc.response.text[:1000]
    return RuntimeError(f"{provider} 搜索失败，HTTP {exc.response.status_code}: {body}")


async def _search_tavily(query: str, limit: int, settings: Settings) -> dict[str, object]:
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


async def _search_duckduckgo(query: str, limit: int, settings: Settings) -> dict[str, object]:
    errors: list[str] = []
    for url in DUCKDUCKGO_SEARCH_URLS:
        try:
            async with httpx.AsyncClient(
                timeout=_request_timeout(settings.request_timeout),
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    url,
                    params={"q": query},
                    headers={"User-Agent": SEARCH_USER_AGENT},
                )
                response.raise_for_status()
                body = response.text
        except httpx.HTTPStatusError as exc:
            raise _http_status_error("DuckDuckGo", exc) from exc
        except httpx.HTTPError as exc:
            errors.append(f"{url}: {exc}")
            continue

        return {
            "provider": "duckduckgo",
            "query": query,
            "answer": "",
            "results": _parse_duckduckgo_results(body, limit),
        }

    raise _provider_failure("DuckDuckGo", errors)


async def _search_bing(query: str, limit: int, settings: Settings) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(
            timeout=_request_timeout(settings.request_timeout),
            follow_redirects=True,
        ) as client:
            response = await client.get(
                BING_SEARCH_URL,
                params={"q": query},
                headers={"User-Agent": SEARCH_USER_AGENT},
            )
            response.raise_for_status()
            body = response.text
    except httpx.HTTPStatusError as exc:
        raise _http_status_error("Bing", exc) from exc
    except httpx.HTTPError as exc:
        raise ConnectionError(f"Bing 搜索失败: {exc}") from exc

    return {
        "provider": "bing",
        "query": query,
        "answer": "",
        "results": _parse_bing_results(body, limit),
    }


async def _search_public_fallbacks(query: str, limit: int, settings: Settings) -> dict[str, object]:
    errors: list[str] = []
    try:
        return await _search_duckduckgo(query, limit, settings)
    except (ConnectionError, RuntimeError) as exc:
        errors.append(str(exc))

    try:
        return await _search_bing(query, limit, settings)
    except (ConnectionError, RuntimeError) as exc:
        errors.append(str(exc))

    raise ConnectionError("自动搜索失败: " + "；".join(errors))


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
            Field(
                title="搜索提供方",
                description="auto 优先使用 Tavily；未配置 Tavily Key 时使用 DuckDuckGo，失败后回退到 Bing。",
            ),
        ] = "auto",
    ) -> dict[str, object]:
        """联网搜索公开网页，返回标题、URL 和摘要。"""
        limit = max(1, min(max_results, 10))
        if provider == "auto":
            if settings.tavily_api_key:
                try:
                    return await _search_tavily(query, limit, settings)
                except ConnectionError:
                    return await _search_public_fallbacks(query, limit, settings)
            return await _search_public_fallbacks(query, limit, settings)

        if provider == "tavily":
            if settings.tavily_api_key:
                return await _search_tavily(query, limit, settings)
            return await _search_public_fallbacks(query, limit, settings)

        if provider == "duckduckgo":
            return await _search_duckduckgo(query, limit, settings)

        return await _search_bing(query, limit, settings)


register_web_tools = register_web_search_tool
