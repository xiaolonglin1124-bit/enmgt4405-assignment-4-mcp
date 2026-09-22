import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import job_tracker_mcp.server as server_module
from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter
from job_tracker_mcp.service import InterviewScheduleService

from .fakes import FakeGmailClient, FakeNotionClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_exposes_required_tools_and_prompt() -> None:
    async def inspect_server() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(PROJECT_ROOT / "server.py")],
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            tools = await client.list_tools()
            prompts = await client.list_prompts()
            rendered = await client.get_prompt(
                "weekly_interview_schedule_review",
                {"week_start": "2026-09-21", "timezone": "America/New_York"},
            )

            assert {tool.name for tool in tools.tools} == {
                "list_weekly_interview_invites",
                "add_interview_to_notion",
            }
            assert {prompt.name for prompt in prompts.prompts} == {
                "weekly_interview_schedule_review"
            }
            assert len(rendered.messages) == 1

    asyncio.run(inspect_server())


def test_mcp_tool_can_be_called_through_server(monkeypatch) -> None:
    service = InterviewScheduleService(
        FakeGmailClient(),
        FakeNotionClient(),
        SlidingWindowRateLimiter(max_calls=20, window_seconds=60),
    )
    monkeypatch.setattr(server_module, "_service", service)

    async def call_tool() -> None:
        _, structured = await server_module.mcp.call_tool(
            "list_weekly_interview_invites",
            {
                "week_start": "2026-09-21",
                "timezone": "America/New_York",
            },
        )

        assert structured["success"] is True
        assert structured["week_start"] == "2026-09-21"

    asyncio.run(call_tool())
