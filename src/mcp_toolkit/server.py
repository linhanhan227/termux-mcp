from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from .core.config import Settings
from .core.http_auth import HeaderAuthMiddleware
from .core.registry import ToolRegistry, load_plugin_modules
from .tools import register_builtin_tools


class ToolkitFastMCP(FastMCP):
    def __init__(self, toolkit_settings: Settings) -> None:
        super().__init__(
            toolkit_settings.server_name,
            host=toolkit_settings.host,
            port=toolkit_settings.port,
            stateless_http=toolkit_settings.stateless_http,
        )
        self.toolkit_settings = toolkit_settings
        self._register_health_route()

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        app = super().sse_app(mount_path)
        return self._with_header_auth(app)

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        return self._with_header_auth(app)

    def _with_header_auth(self, app: Starlette) -> Starlette:
        if self.toolkit_settings.auth_token:
            app.add_middleware(
                HeaderAuthMiddleware,
                header_name=self.toolkit_settings.auth_header,
                token=self.toolkit_settings.auth_token,
            )
        return app

    def _register_health_route(self) -> None:
        @self.custom_route("/healthz", methods=["GET"], include_in_schema=False)
        async def healthz(request: Request) -> JSONResponse:
            settings = self.toolkit_settings
            return JSONResponse(
                {
                    "status": "ok",
                    "server_name": settings.server_name,
                    "transport": settings.transport,
                    "workspace": str(settings.workspace),
                    "allow_write": settings.allow_write,
                    "auth_enabled": bool(settings.auth_token),
                    "stateless_http": settings.stateless_http,
                }
            )


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    server = ToolkitFastMCP(settings)

    registry = ToolRegistry()
    register_builtin_tools(registry, settings)
    load_plugin_modules(registry, settings, settings.plugin_modules)
    registry.register_to(server)

    return server


def _csv_items(values: Sequence[str] | None) -> tuple[str, ...] | None:
    if not values:
        return None
    items: list[str] = []
    for value in values:
        items.extend(item.strip() for item in value.split(",") if item.strip())
    return tuple(items)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Python MCP Toolkit Server.")
    parser.add_argument(
        "--env-file",
        help="Path to an env file to load before reading MCP_* settings. Defaults to .env in the current directory.",
    )
    parser.add_argument("--transport", choices=("stdio", "sse", "streamable-http"), help="MCP transport to run.")
    parser.add_argument("--host", help="HTTP/SSE host to bind, for example 127.0.0.1 or 0.0.0.0.")
    parser.add_argument("--port", type=int, help="HTTP/SSE port to bind.")
    parser.add_argument("--workspace", type=Path, help="Workspace root for file and shell tools.")
    parser.add_argument("--auth-token", help="HTTP/SSE header token. Empty or omitted disables header auth.")
    parser.add_argument("--auth-header", help="HTTP header name used for the auth token.")
    parser.add_argument(
        "--stateless-http",
        action="store_true",
        help="Do not require MCP session headers for streamable-http requests.",
    )
    parser.add_argument(
        "--stateful-http",
        action="store_true",
        help="Require MCP session headers for streamable-http requests.",
    )
    parser.add_argument("--plugin", action="append", help="Plugin module to load. May be repeated or comma-separated.")
    parser.add_argument("--allow-write", action="store_true", help="Enable file_operation write/copy/move/delete actions.")
    parser.add_argument("--disable-write", action="store_true", help="Disable file_operation write/copy/move/delete actions.")
    parser.add_argument("--show-config", action="store_true", help="Print resolved non-secret configuration and exit.")
    return parser


def settings_from_args(argv: Sequence[str] | None = None) -> tuple[Settings, bool]:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.env_file:
        os.environ["MCP_ENV_FILE"] = args.env_file

    settings = Settings.from_env()

    updates: dict[str, object] = {}
    if args.transport:
        updates["transport"] = args.transport
    if args.host:
        updates["host"] = args.host
    if args.port is not None:
        updates["port"] = args.port
    if args.workspace is not None:
        updates["workspace"] = args.workspace.expanduser().resolve()
    if args.auth_token is not None:
        updates["auth_token"] = args.auth_token or None
    if args.auth_header:
        updates["auth_header"] = args.auth_header
    if args.stateless_http and args.stateful_http:
        parser.error("--stateless-http and --stateful-http cannot be used together")
    if args.stateless_http:
        updates["stateless_http"] = True
    if args.stateful_http:
        updates["stateless_http"] = False

    plugins = _csv_items(args.plugin)
    if plugins is not None:
        updates["plugin_modules"] = plugins

    if args.allow_write and args.disable_write:
        parser.error("--allow-write and --disable-write cannot be used together")
    if args.allow_write:
        updates["allow_write"] = True
    if args.disable_write:
        updates["allow_write"] = False

    return replace(settings, **updates), args.show_config


def _public_config(settings: Settings) -> dict[str, object]:
    return {
        "server_name": settings.server_name,
        "transport": settings.transport,
        "host": settings.host,
        "port": settings.port,
        "workspace": str(settings.workspace),
        "tavily_api_configured": bool(settings.tavily_api_key),
        "auth_enabled": bool(settings.auth_token),
        "auth_header": settings.auth_header,
        "allow_write": settings.allow_write,
        "max_file_bytes": settings.max_file_bytes,
        "request_timeout": settings.request_timeout,
        "plugin_modules": list(settings.plugin_modules),
        "stateless_http": settings.stateless_http,
    }


def main(argv: Sequence[str] | None = None) -> None:
    settings, show_config = settings_from_args(argv)
    if show_config:
        print(json.dumps(_public_config(settings), ensure_ascii=False, indent=2))
        return

    create_server(settings).run(transport=settings.transport)


if __name__ == "__main__":
    main()
