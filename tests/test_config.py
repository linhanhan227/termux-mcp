from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp_toolkit.core.config import Settings


@contextmanager
def chdir(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class SettingsTests(unittest.TestCase):
    def test_loads_dotenv_from_current_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "MCP_TRANSPORT=streamable-http",
                        "MCP_HOST=0.0.0.0",
                        "MCP_PORT=9000",
                        "MCP_AUTH_TOKEN='secret'",
                        "MCP_AUTH_HEADER=X-Test-Auth",
                        "MCP_STATELESS_HTTP=false",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), chdir(root):
                settings = Settings.from_env()

        self.assertEqual(settings.transport, "streamable-http")
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.auth_token, "secret")
        self.assertEqual(settings.auth_header, "X-Test-Auth")
        self.assertFalse(settings.stateless_http)

    def test_streamable_http_is_stateless_by_default(self) -> None:
        with patch.dict(os.environ, {"MCP_ENV_FILE": ""}, clear=True):
            settings = Settings.from_env()

        self.assertTrue(settings.stateless_http)

    def test_environment_wins_over_dotenv(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("MCP_AUTH_TOKEN=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"MCP_AUTH_TOKEN": "from-env"}, clear=True), chdir(root):
                settings = Settings.from_env()

        self.assertEqual(settings.auth_token, "from-env")

    def test_blank_tavily_api_key_is_treated_as_missing(self) -> None:
        with patch.dict(os.environ, {"MCP_ENV_FILE": "", "TAVILY_API_KEY": "   "}, clear=True):
            settings = Settings.from_env()

        self.assertIsNone(settings.tavily_api_key)

    def test_rejects_invalid_transport(self) -> None:
        with patch.dict(os.environ, {"MCP_ENV_FILE": "", "MCP_TRANSPORT": "bad"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
