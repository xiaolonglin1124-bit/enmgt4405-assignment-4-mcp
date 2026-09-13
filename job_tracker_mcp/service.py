"""Business logic kept separate from the MCP protocol layer."""

from typing import Any

from .notion_client import NotionJobClient
from .rate_limiter import SlidingWindowRateLimiter
from .validators import (
    validate_iso_date,
    validate_limit,
    validate_optional_date,
    validate_optional_text,
    validate_status,
    validate_text,
    validate_url,
)


class JobApplicationService:
    def __init__(
        self,
        notion: NotionJobClient,
        limiter: SlidingWindowRateLimiter,
    ) -> None:
        self._notion = notion
        self._limiter = limiter

    def add_job_application(
        self,
        *,
        company: str,
        role: str,
        job_url: str,
        applied_date: str,
        follow_up_date: str | None = None,
        notes: str = "",
        status: str = "Applied",
    ) -> dict[str, Any]:
        self._limiter.check("add_job_application")
        validated = {
            "company": validate_text(company, "company", 200),
            "role": validate_text(role, "role", 200),
            "job_url": validate_url(job_url),
            "applied_date": validate_iso_date(applied_date, "applied_date"),
            "follow_up_date": validate_optional_date(
                follow_up_date, "follow_up_date"
            ),
            "notes": validate_optional_text(notes, "notes", 2000),
            "status": validate_status(status),
        }
        result = self._notion.create_application(**validated)
        return {"success": True, "application": result}

    def list_job_applications(
        self,
        *,
        status: str = "All",
        follow_up_before: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        self._limiter.check("list_job_applications")
        validated_status = validate_status(status, allow_all=True)
        validated_date = validate_optional_date(
            follow_up_before, "follow_up_before"
        )
        validated_limit = validate_limit(limit)
        results = self._notion.list_applications(
            status=validated_status,
            follow_up_before=validated_date,
            limit=validated_limit,
        )
        return {
            "success": True,
            "count": len(results),
            "applications": results,
        }
