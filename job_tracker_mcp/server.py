"""MCP protocol layer exposing two tools and one prompt."""

from collections.abc import Callable
import logging
from typing import Any

from mcp.server import MCPServer

from .config import ConfigurationError, load_settings
from .errors import ExternalServiceError, RateLimitExceeded, ValidationError
from .notion_client import NotionJobClient
from .rate_limiter import SlidingWindowRateLimiter
from .service import JobApplicationService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCPServer, decorators, and stdio run pattern are based on the official MCP
# Python SDK documentation: https://github.com/modelcontextprotocol/python-sdk
mcp = MCPServer("Job Application Tracker")
_service: JobApplicationService | None = None


def _get_service() -> JobApplicationService:
    global _service
    if _service is None:
        settings = load_settings()
        notion = NotionJobClient(
            settings.notion_token,
            settings.notion_data_source_id,
        )
        limiter = SlidingWindowRateLimiter(
            settings.rate_limit_calls,
            settings.rate_limit_window_seconds,
        )
        _service = JobApplicationService(notion, limiter)
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
        logger.error("External job application service request failed")
        return {
            "success": False,
            "error_code": "EXTERNAL_SERVICE_ERROR",
            "message": "Unable to access the job application database.",
        }
    except Exception:
        # Deliberately omit exception text and traceback: either could contain a
        # token, request header, local path, or third-party response body.
        logger.error("Unexpected internal tool failure")
        return {
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "The operation could not be completed.",
        }


@mcp.tool()
def add_job_application(
    company: str,
    role: str,
    job_url: str,
    applied_date: str,
    follow_up_date: str | None = None,
    notes: str = "",
    status: str = "Applied",
) -> dict[str, Any]:
    """Add a job application to the configured Notion data source.

    Dates must use YYYY-MM-DD. Status may be Wishlist, Applied, Interview,
    Offer, Rejected, or Withdrawn.
    """
    return _safe_tool_call(
        lambda: _get_service().add_job_application(
            company=company,
            role=role,
            job_url=job_url,
            applied_date=applied_date,
            follow_up_date=follow_up_date,
            notes=notes,
            status=status,
        )
    )


@mcp.tool()
def list_job_applications(
    status: str = "All",
    follow_up_before: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List job applications, optionally filtered by status and follow-up date.

    Status may be All, Wishlist, Applied, Interview, Offer, Rejected, or
    Withdrawn. follow_up_before must use YYYY-MM-DD.
    """
    return _safe_tool_call(
        lambda: _get_service().list_job_applications(
            status=status,
            follow_up_before=follow_up_before,
            limit=limit,
        )
    )


@mcp.prompt()
def weekly_job_search_review(days: int = 7) -> str:
    """Guide Claude through a structured review of job applications."""
    safe_days = min(max(days, 1), 30)
    return f"""You are helping the user review their job search for the next {safe_days} days.

1. Ask for today's date if it is not available in the conversation.
2. Use list_job_applications to retrieve relevant applications.
3. Identify overdue and upcoming follow-ups.
4. Group applications by status and prioritize concrete next actions.
5. Produce a concise {safe_days}-day plan with dates.
6. Never add or change an application without explicit user confirmation.
7. Do not invent company responses, deadlines, or application details.
"""


def main() -> None:
    """Run the local server over stdio, the default MCP transport."""
    mcp.run()
