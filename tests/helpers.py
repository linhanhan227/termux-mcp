from __future__ import annotations

from pathlib import Path

from mcp_toolkit.core.config import Settings


def make_settings(
    workspace: Path,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    auth_token: str | None = None,
    auth_header: str = "X-MCP-Auth-Token",
    allow_write: bool = False,
    stateless_http: bool = True,
) -> Settings:
    return Settings(
        server_name="test-mcp",
        transport=transport,  # type: ignore[arg-type]
        host=host,
        port=port,
        workspace=workspace.resolve(),
        tavily_api_key=None,
        tavily_api_url="https://api.tavily.com/search",
        auth_token=auth_token,
        auth_header=auth_header,
        allow_write=allow_write,
        max_file_bytes=1024 * 1024,
        request_timeout=5.0,
        plugin_modules=(),
        stateless_http=stateless_http,
    )
