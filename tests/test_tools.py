from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_toolkit.core.registry import ToolRegistry
from mcp_toolkit.core.security import resolve_workspace_path
from mcp_toolkit.tools.agent import register_agent_tool
from mcp_toolkit.tools.files import register_file_operation_tool
from mcp_toolkit.tools.web import _parse_duckduckgo_results

from tests.helpers import make_settings


def tool(registry: ToolRegistry, name: str):
    return next(spec.handler for spec in registry.tools if spec.name == name)


class ToolTests(unittest.TestCase):
    def test_workspace_paths_cannot_escape_root(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            resolved = resolve_workspace_path(workspace, "inside.txt")
            self.assertEqual(resolved, workspace / "inside.txt")

            with self.assertRaises(ValueError):
                resolve_workspace_path(workspace, "../outside.txt")

    def test_file_operation_respects_write_flag(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            register_file_operation_tool(registry, make_settings(workspace, allow_write=False))

            file_operation = tool(registry, "file_operation")
            with self.assertRaises(PermissionError):
                file_operation("write", path="note.txt", content="blocked")

    def test_file_operation_covers_common_file_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            registry = ToolRegistry()
            register_file_operation_tool(registry, make_settings(workspace, allow_write=True))
            file_operation = tool(registry, "file_operation")

            file_operation("write", path="docs/note.txt", content="one\ntwo\nthree\n")
            info = file_operation("info", path="docs/note.txt", include_hash=True)
            self.assertEqual(info["sha256"], hashlib.sha256(b"one\ntwo\nthree\n").hexdigest())

            lines = file_operation("read_lines", path="docs/note.txt", start_line=2, max_lines=1)
            self.assertEqual(lines["lines"][0]["text"], "two")

            replace = file_operation("replace", path="docs/note.txt", content="two", replacement="TWO")
            self.assertEqual(replace["replacements"], 1)
            self.assertIn("TWO", file_operation("read", path="docs/note.txt")["content"])

            file_operation("mkdir", path="tmp/nested")
            self.assertTrue((workspace / "tmp" / "nested").is_dir())
            file_operation("copy", path="docs/note.txt", destination="tmp/copy.txt")
            file_operation("move", path="tmp/copy.txt", destination="tmp/moved.txt")
            self.assertTrue((workspace / "tmp" / "moved.txt").is_file())

            grep = file_operation("grep", path=".", pattern="*.txt", query="TWO")
            self.assertEqual(grep["matches"][0]["path"], "docs/note.txt")

            file_operation("delete", path="tmp", recursive=True)
            self.assertFalse((workspace / "tmp").exists())
            with self.assertRaises(PermissionError):
                file_operation("delete", path=".", recursive=True)

    def test_agent_tracks_task_state(self) -> None:
        registry = ToolRegistry()
        with TemporaryDirectory() as tmp:
            register_agent_tool(registry, make_settings(Path(tmp)))
        agent = tool(registry, "agent")

        started = agent("start", task="整理项目文档", steps=["阅读", "修改", "验证"])
        self.assertTrue(started["active"])
        self.assertEqual(started["steps"], ["阅读", "修改", "验证"])

        updated = agent("update", note="已完成阅读")
        self.assertEqual(updated["notes"][0]["text"], "已完成阅读")

        finished = agent("finish", note="完成")
        self.assertFalse(finished["active"])
        self.assertEqual(finished["status"], "finished")

        reset = agent("reset")
        self.assertEqual(reset["status"], "idle")

    def test_duckduckgo_result_parser_normalizes_redirects(self) -> None:
        body = """
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">Example &amp; A</a>
        <a class="result__a" href="https://example.org/b">Example B</a>
        """
        results = _parse_duckduckgo_results(body, 10)
        self.assertEqual(results[0]["title"], "Example & A")
        self.assertEqual(results[0]["url"], "https://example.com/a")
        self.assertEqual(results[1]["url"], "https://example.org/b")


if __name__ == "__main__":
    unittest.main()
