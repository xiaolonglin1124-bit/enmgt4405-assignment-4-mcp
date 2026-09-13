import asyncio

from mcp import Client

from job_tracker_mcp.server import mcp


def test_mcp_exposes_required_tools_and_prompt() -> None:
    async def inspect_server() -> None:
        async with Client(mcp) as client:
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
