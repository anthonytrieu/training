"""Claude coach chat over SSE, powered by the Claude Agent SDK.

Uses the local Claude Code login (subscription auth) — no API key. Each browser
chat session keeps one connected ClaudeSDKClient so multi-turn context and the
spawned MCP server survive across messages. The agent gets ONLY the read-only
garmin MCP tools: no bash, no file access.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    ToolUseBlock,
)
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api")

GARMIN_MCP = str(Path(sys.executable).parent / "garmin-mcp")
PLAN_DIR = Path(__file__).resolve().parents[3] / "training"

COACH_RULES = """You are the user's personal cycling coach, speaking through their private
training web app. Data access: read-only Garmin tools (mcp__garmin__*).

The athlete: Garmin Edge 540, Rally RS100 single-sided power meter, FTP 290 W,
training for the RBC GranFondo Whistler on September 12, 2026 (~122 km, ~1,700-2,000 m
of sustained climbing).

Coaching rules — always:
- Distinguish recorded facts, calculated values, and coaching interpretation.
- Fetch real data with the tools before making data-based claims; if data is missing
  or conflicting, say so instead of guessing.
- Power is single-sided (left-leg doubled): never discuss left/right balance and treat
  watt targets as approximately +/-5-10 W.
- Anchor intensity to the current FTP from the tools; never invent zone boundaries.
- Training readiness / recovery time are unavailable (no Garmin watch) — reason from
  sleep, HRV, resting HR and load instead.
- No medical diagnoses.
- Keep answers conversational and practical; lead with the answer, then the evidence.
- Never schedule or upload workouts; plans are advice in chat only.
"""


def _system_prompt() -> str:
    prompt = COACH_RULES
    plans = sorted(PLAN_DIR.glob("*.md")) if PLAN_DIR.exists() else []
    if plans:
        prompt += (
            "\n\nThe athlete's current training plan (reference it when relevant):\n\n"
            + plans[-1].read_text()
        )
    return prompt


# Built-in / harness tools the coach must not use. ToolSearch stays available:
# Claude Code 2.1+ defers MCP tool schemas behind it, so removing it would hide
# the garmin tools entirely.
DISALLOWED_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
    "Task",
    "TodoWrite",
    "Skill",
    "Workflow",
    "SendMessage",
    "EnterWorktree",
    "ExitWorktree",
]


def _options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model="claude-opus-4-8",
        system_prompt=_system_prompt(),
        mcp_servers={"garmin": {"type": "stdio", "command": GARMIN_MCP}},
        strict_mcp_config=True,  # never load the user's other MCP servers
        allowed_tools=["mcp__garmin"],  # every tool from the garmin server
        disallowed_tools=DISALLOWED_TOOLS,
        include_partial_messages=True,
        max_turns=30,
    )


@dataclass
class ChatSession:
    client: ClaudeSDKClient
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_sessions: dict[str, ChatSession] = {}

TOOL_LABELS = {
    "get_recent_activities": "Looking up recent rides",
    "get_activity_summary": "Reading ride details",
    "get_activity_splits": "Checking lap splits",
    "get_activity_power_data": "Analyzing power zones",
    "get_activity_heart_rate_data": "Analyzing heart-rate zones",
    "get_activity_details": "Examining ride data streams",
    "compare_activities": "Comparing rides",
    "get_training_status": "Checking training status",
    "get_training_readiness": "Checking readiness",
    "get_recovery_time": "Checking recovery",
    "get_hrv_history": "Reviewing HRV",
    "get_sleep_history": "Reviewing sleep",
    "get_resting_heart_rate_history": "Reviewing resting heart rate",
    "get_vo2_max": "Checking VO2 max",
    "get_current_ftp": "Checking FTP",
    "get_fitness_age": "Checking fitness age",
    "get_weekly_training_summary": "Summarizing recent weeks",
    "get_training_plan_context": "Gathering training context",
}


def _tool_label(tool_name: str) -> str:
    short = tool_name.removeprefix("mcp__garmin__")
    return TOOL_LABELS.get(short, f"Using {short}")


async def _get_session(session_id: str) -> ChatSession:
    session = _sessions.get(session_id)
    if session is None:
        client = ClaudeSDKClient(options=_options())
        await client.connect()
        session = ChatSession(client=client)
        _sessions[session_id] = session
    return session


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


async def _stream_reply(req: ChatRequest) -> AsyncIterator[str]:
    session_id = req.session_id or uuid4().hex
    try:
        session = await _get_session(session_id)
    except Exception as e:  # CLI missing / not logged in
        yield _sse(
            {
                "type": "error",
                "message": (
                    f"Could not start the Claude agent: {e}. "
                    "Make sure Claude Code is installed and logged in."
                ),
            }
        )
        return

    async with session.lock:
        try:
            await session.client.query(req.message)
            async for message in session.client.receive_response():
                if isinstance(message, StreamEvent):
                    event = message.event
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield _sse({"type": "text", "text": delta["text"]})
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        # ToolSearch is plumbing (deferred MCP tool discovery) — not
                        # worth surfacing as coach activity.
                        if isinstance(block, ToolUseBlock) and block.name != "ToolSearch":
                            yield _sse({"type": "tool", "label": _tool_label(block.name)})
                elif isinstance(message, ResultMessage):
                    yield _sse({"type": "done", "session_id": session_id})
        except Exception as e:
            yield _sse({"type": "error", "message": f"Chat failed: {e}"})
            _sessions.pop(session_id, None)


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_stream_reply(req), media_type="text/event-stream")
