from __future__ import annotations

import asyncio
import unittest
import warnings
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`.*")
logging.disable(logging.CRITICAL)

from starlette.testclient import TestClient

from mcp_toolkit.server import create_server, settings_from_args

from tests.helpers import make_settings


class ServerTests(unittest.TestCase):
    def test_cli_args_override_environment(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            env = {
                "MCP_ENV_FILE": "",
                "MCP_TRANSPORT": "stdio",
                "MCP_HOST": "127.0.0.1",
                "MCP_PORT": "8000",
            }
            argv = [
                "--transport",
                "streamable-http",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--workspace",
                str(workspace),
                "--auth-token",
                "secret",
                "--stateful-http",
                "--plugin",
                "examples.custom_tools,examples.math_tools",
            ]
            with patch.dict("os.environ", env, clear=True):
                settings, show_config = settings_from_args(argv)

        self.assertFalse(show_config)
        self.assertEqual(settings.transport, "streamable-http")
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.auth_token, "secret")
        self.assertFalse(settings.stateless_http)
        self.assertEqual(settings.plugin_modules, ("examples.custom_tools", "examples.math_tools"))

    def test_builtin_tool_metadata_is_chinese(self) -> None:
        with TemporaryDirectory() as tmp:
            server = create_server(make_settings(Path(tmp)))
            tools = asyncio.run(server.list_tools())

        by_name = {tool.name: tool for tool in tools}
        self.assertEqual(list(by_name), ["web_search", "file_operation", "agent"])

        web_search = by_name["web_search"]
        file_operation = by_name["file_operation"]
        agent = by_name["agent"]

        self.assertIn("联网搜索", web_search.description)
        self.assertEqual(web_search.inputSchema["properties"]["query"]["title"], "搜索词")
        self.assertEqual(file_operation.inputSchema["properties"]["action"]["title"], "操作")
        self.assertIn("文件操作类型", file_operation.inputSchema["properties"]["action"]["description"])
        self.assertEqual(agent.inputSchema["properties"]["action"]["title"], "动作")

    def test_streamable_http_does_not_require_session_header_by_default(self) -> None:
        headers = {
            "host": "127.0.0.1:8000",
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        with TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp), transport="streamable-http")
            app = create_server(settings).streamable_http_app()
            with TestClient(app) as client:
                response = client.post("/mcp", headers=headers, json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mcp-session-id", response.headers)
        self.assertIn('"tools"', response.text)

    def test_stateful_streamable_http_requires_session_header(self) -> None:
        headers = {
            "host": "127.0.0.1:8000",
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        with TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp), transport="streamable-http", stateless_http=False)
            app = create_server(settings).streamable_http_app()
            with TestClient(app) as client:
                response = client.post("/mcp", headers=headers, json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing session ID", response.text)

    def test_streamable_http_requires_configured_header(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = make_settings(
                Path(tmp),
                transport="streamable-http",
                auth_token="secret",
                auth_header="X-MCP-Auth-Token",
            )
            app = create_server(settings).streamable_http_app()
            with TestClient(app) as client:
                missing = client.get("/healthz")
                wrong = client.get("/healthz", headers={"X-MCP-Auth-Token": "wrong"})
                ok = client.get("/healthz", headers={"X-MCP-Auth-Token": "secret"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "ok")
        self.assertTrue(ok.json()["auth_enabled"])

    def test_authorization_bearer_header_is_supported(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = make_settings(
                Path(tmp),
                transport="streamable-http",
                auth_token="secret",
                auth_header="Authorization",
            )
            app = create_server(settings).streamable_http_app()
            with TestClient(app) as client:
                response = client.get("/healthz", headers={"Authorization": "Bearer secret"})

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
