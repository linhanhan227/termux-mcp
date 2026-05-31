from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field

from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


AgentAction = Literal["start", "status", "update", "finish", "reset"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_agent_tool(registry: ToolRegistry, settings: Settings) -> None:
    state: dict[str, object] = {
        "active": False,
        "task": "",
        "status": "idle",
        "steps": [],
        "notes": [],
        "created_at": "",
        "updated_at": "",
    }

    @registry.tool()
    def agent(
        action: Annotated[
            AgentAction,
            Field(title="动作", description="agent 动作：start/status/update/finish/reset。"),
        ] = "status",
        task: Annotated[str | None, Field(title="任务", description="start 时设置的任务目标。")] = None,
        steps: Annotated[
            list[str] | None,
            Field(title="步骤", description="start 时设置的执行步骤；为空时使用默认执行步骤。"),
        ] = None,
        note: Annotated[str | None, Field(title="记录", description="update/finish 时追加的进展、观察或结论。")] = None,
    ) -> dict[str, object]:
        """管理一个轻量 agent 任务状态，用于记录目标、步骤、进展和完成结果。"""
        now = _now_iso()

        if action == "start":
            task_text = (task or "").strip()
            if not task_text:
                raise ValueError("start 动作需要提供 task")
            state.update(
                {
                    "active": True,
                    "task": task_text,
                    "status": "running",
                    "steps": steps
                    or [
                        "确认目标和约束",
                        "收集必要上下文",
                        "执行任务",
                        "验证结果并整理输出",
                    ],
                    "notes": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )
            return dict(state)

        if action == "status":
            return dict(state)

        if action == "update":
            if not state["active"]:
                raise RuntimeError("当前没有运行中的 agent 任务")
            if note:
                notes = list(state["notes"])
                notes.append({"time": now, "text": note})
                state["notes"] = notes
            state["updated_at"] = now
            return dict(state)

        if action == "finish":
            if not state["active"]:
                raise RuntimeError("当前没有运行中的 agent 任务")
            if note:
                notes = list(state["notes"])
                notes.append({"time": now, "text": note})
                state["notes"] = notes
            state["active"] = False
            state["status"] = "finished"
            state["updated_at"] = now
            return dict(state)

        if action == "reset":
            state.update(
                {
                    "active": False,
                    "task": "",
                    "status": "idle",
                    "steps": [],
                    "notes": [],
                    "created_at": "",
                    "updated_at": now,
                }
            )
            return dict(state)

        raise ValueError(f"未知 agent 动作: {action}")
