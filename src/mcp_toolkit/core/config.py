from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Transport = Literal["stdio", "sse", "streamable-http"]
_TRANSPORTS: set[str] = {"stdio", "sse", "streamable-http"}


def _load_env_file() -> None:
    env_file = os.getenv("MCP_ENV_FILE", ".env").strip()
    if not env_file:
        return

    path = Path(env_file).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_optional_str(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _env_transport(name: str, default: Transport) -> Transport:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if value not in _TRANSPORTS:
        allowed = ", ".join(sorted(_TRANSPORTS))
        raise ValueError(f"{name} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def _env_header_name(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value or ":" in value or "\r" in value or "\n" in value:
        raise ValueError(f"{name} must be a valid HTTP header name")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    server_name: str
    transport: Transport
    host: str
    port: int
    workspace: Path
    tavily_api_key: str | None
    tavily_api_url: str
    auth_token: str | None
    auth_header: str
    allow_write: bool
    max_file_bytes: int
    request_timeout: float
    plugin_modules: tuple[str, ...]
    stateless_http: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_file()
        workspace = Path(os.getenv("MCP_WORKSPACE", ".")).expanduser().resolve()
        return cls(
            server_name=os.getenv("MCP_SERVER_NAME", "python-mcp-toolkit"),
            transport=_env_transport("MCP_TRANSPORT", "stdio"),
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=_env_int("MCP_PORT", 8000),
            workspace=workspace,
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            tavily_api_url=os.getenv("TAVILY_API_URL", "https://api.tavily.com/search"),
            auth_token=_env_optional_str("MCP_AUTH_TOKEN"),
            auth_header=_env_header_name("MCP_AUTH_HEADER", "X-MCP-Auth-Token"),
            allow_write=_env_bool("MCP_ALLOW_WRITE", False),
            max_file_bytes=_env_int("MCP_MAX_FILE_BYTES", 2 * 1024 * 1024),
            request_timeout=_env_float("MCP_REQUEST_TIMEOUT", 20.0),
            plugin_modules=_env_csv("MCP_TOOLKIT_PLUGINS"),
            stateless_http=_env_bool("MCP_STATELESS_HTTP", True),
        )
