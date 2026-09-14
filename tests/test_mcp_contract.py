import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import job_tracker_mcp.server as server_module
from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter
from job_tracker_mcp.service import JobApplicationService

from .fakes import FakeNotionClient

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
                "weekly_job_search_review", {"days": "7"}
            )

            assert {tool.name for tool in tools.tools} == {
                "add_job_application",
                "list_job_applications",
            }
            assert {prompt.name for prompt in prompts.prompts} == {
                "weekly_job_search_review"
            }
            assert len(rendered.messages) == 1

    asyncio.run(inspect_server())


def test_mcp_tool_can_be_called_through_server(monkeypatch) -> None:
    notion = FakeNotionClient()
    service = JobApplicationService(
        notion,
        SlidingWindowRateLimiter(max_calls=20, window_seconds=60),
    )
    monkeypatch.setattr(server_module, "_service", service)

    async def call_tool() -> None:
        _, structured = await server_module.mcp.call_tool(
            "add_job_application",
            {
                "company": "Adobe",
                "role": "Product Designer",
                "job_url": "https://example.com/jobs/123",
                "applied_date": "2026-09-13",
            },
        )

        assert structured["success"] is True
        assert structured["application"]["company"] == "Adobe"

    asyncio.run(call_tool())
