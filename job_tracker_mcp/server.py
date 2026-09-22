"""MCP protocol layer exposing two tools and one prompt."""

import logging
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ConfigurationError, load_settings
from .errors import ExternalServiceError, RateLimitExceeded, ValidationError
from .gmail_client import GmailInterviewClient
from .notion_client import NotionScheduleClient
from .rate_limiter import SlidingWindowRateLimiter
from .service import InterviewScheduleService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP decorators and the stdio run pattern follow the official MCP Python
# SDK documentation: https://github.com/modelcontextprotocol/python-sdk/tree/v1.x
mcp = FastMCP("Gmail Interview Scheduler")
_service: InterviewScheduleService | None = None


def _get_service() -> InterviewScheduleService:
    global _service
    if _service is None:
        settings = load_settings()
        gmail = GmailInterviewClient.from_token(settings.gmail_token_path)
        notion = NotionScheduleClient(
            settings.notion_token,
            settings.notion_interview_data_source_id,
        )
        limiter = SlidingWindowRateLimiter(
            settings.rate_limit_calls,
            settings.rate_limit_window_seconds,
        )
        _service = InterviewScheduleService(gmail, notion, limiter)
    return _service


def _safe_tool_call(operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Translate internal failures into intentionally small public errors."""
    try:
        return operation()
    except ValidationError as exc:
        return {
            "success": False,
            "error_code": "INVALID_INPUT",
            "message": str(exc),
        }
    except RateLimitExceeded as exc:
        return {
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many tool calls. Please try again later.",
            "retry_after_seconds": exc.retry_after_seconds,
        }
    except ConfigurationError:
        logger.error("MCP server configuration is incomplete")
        return {
            "success": False,
            "error_code": "CONFIGURATION_ERROR",
            "message": "The server is not configured. Follow the README setup steps.",
        }
    except ExternalServiceError:
        logger.error("External Gmail or Notion request failed")
        return {
            "success": False,
            "error_code": "EXTERNAL_SERVICE_ERROR",
            "message": "Unable to access Gmail or the Notion interview schedule.",
        }
    except Exception:  # noqa: BLE001 - final public safety boundary
        # Never expose exception text or tracebacks: they can contain OAuth
        # tokens, email content, request headers, local paths, or API responses.
        logger.error("Unexpected internal tool failure")
        return {
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "The operation could not be completed.",
        }


@mcp.tool()
def list_weekly_interview_invites(
    week_start: str | None = None,
    timezone: str = "America/New_York",
    lookback_days: int = 90,
    limit: int = 50,
) -> dict[str, Any]:
    """Read Gmail and list interview invitations scheduled for one week.

    week_start may be any date within the desired week and must use YYYY-MM-DD.
    Calendar-backed invitations are returned separately from emails that need
    manual review. This tool never changes Gmail or Notion.
    """
    return _safe_tool_call(
        lambda: _get_service().list_weekly_interview_invites(
            week_start=week_start,
            timezone=timezone,
            lookback_days=lookback_days,
            limit=limit,
        )
    )


@mcp.tool()
def add_interview_to_notion(
    message_id: str,
    company: str,
    role: str,
    start_time: str,
    end_time: str | None = None,
    title: str = "Interview",
    location: str = "",
    meeting_url: str = "",
    recruiter: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Add one user-confirmed Gmail interview invitation to Notion.

    start_time and end_time must be ISO 8601 date-times with timezone offsets.
    Reusing a Gmail message ID is safe: duplicate rows are not created.
    """
    return _safe_tool_call(
        lambda: _get_service().add_interview_to_notion(
            message_id=message_id,
            company=company,
            role=role,
            start_time=start_time,
            end_time=end_time,
            title=title,
            location=location,
            meeting_url=meeting_url,
            recruiter=recruiter,
            notes=notes,
        )
    )


@mcp.prompt()
def weekly_interview_schedule_review(
    week_start: str = "this week",
    timezone: str = "America/New_York",
) -> str:
    """Guide Claude through reviewing Gmail invites and syncing them safely."""
    return f"""Help the user build their interview schedule for {week_start} in {timezone}.

1. Call list_weekly_interview_invites for the requested week and timezone.
2. Show calendar-backed invitations in chronological order.
3. Show needs_review emails separately; never invent a missing time, company, or role.
4. Ask the user to confirm which invitations should be written to Notion.
5. Only after confirmation, call add_interview_to_notion once per confirmed interview.
6. Report duplicates as already scheduled rather than treating them as failures.
7. Finish with a concise preparation checklist and any scheduling conflicts.
"""


def main() -> None:
    """Run the local server over stdio, the default MCP transport."""
    mcp.run()
