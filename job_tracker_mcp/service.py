"""Business logic kept separate from Gmail, Notion, and MCP protocol details."""

from datetime import datetime, time, timedelta
from typing import Any

from .gmail_client import GmailInterviewClient
from .notion_client import NotionScheduleClient
from .rate_limiter import SlidingWindowRateLimiter
from .validators import (
    validate_datetime_range,
    validate_iso_date,
    validate_limit,
    validate_optional_text,
    validate_optional_url,
    validate_text,
    validate_timezone,
)


class InterviewScheduleService:
    def __init__(
        self,
        gmail: GmailInterviewClient,
        notion: NotionScheduleClient,
        limiter: SlidingWindowRateLimiter,
    ) -> None:
        self._gmail = gmail
        self._notion = notion
        self._limiter = limiter

    def list_weekly_interview_invites(
        self,
        *,
        week_start: str | None = None,
        timezone: str = "America/New_York",
        lookback_days: int = 90,
        limit: int = 50,
    ) -> dict[str, Any]:
        self._limiter.check("list_weekly_interview_invites")
        zone = validate_timezone(timezone)
        if week_start:
            requested_date = datetime.fromisoformat(
                validate_iso_date(week_start, "week_start")
            ).date()
        else:
            requested_date = datetime.now(zone).date()
        monday = requested_date - timedelta(days=requested_date.weekday())
        start = datetime.combine(monday, time.min, tzinfo=zone)
        end = start + timedelta(days=7)
        if not 1 <= lookback_days <= 365:
            from .errors import ValidationError

            raise ValidationError("lookback_days must be between 1 and 365.")
        validated_limit = validate_limit(limit)
        invitations = self._gmail.list_weekly_interviews(
            week_start=start,
            week_end=end,
            lookback_days=lookback_days,
            limit=validated_limit,
        )
        return {
            "success": True,
            "week_start": start.date().isoformat(),
            "week_end_exclusive": end.date().isoformat(),
            "timezone": str(zone),
            "scheduled_count": len(invitations["scheduled"]),
            "needs_review_count": len(invitations["needs_review"]),
            **invitations,
        }

    def add_interview_to_notion(
        self,
        *,
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
        self._limiter.check("add_interview_to_notion")
        validated_message_id = validate_text(message_id, "message_id", 200)
        validated_company = validate_text(company, "company", 200)
        validated_role = validate_text(role, "role", 200)
        validated_title = validate_text(title, "title", 300)
        validated_start, validated_end = validate_datetime_range(start_time, end_time)
        validated_location = validate_optional_text(location, "location", 500)
        validated_meeting_url = validate_optional_url(meeting_url, "meeting_url")
        validated_recruiter = validate_optional_text(recruiter, "recruiter", 300)
        validated_notes = validate_optional_text(notes, "notes", 2000)

        existing = self._notion.find_by_gmail_message_id(validated_message_id)
        if existing:
            return {
                "success": True,
                "created": False,
                "message": "This Gmail invitation is already in the Notion schedule.",
                "interview": existing,
            }

        result = self._notion.create_interview(
            message_id=validated_message_id,
            company=validated_company,
            role=validated_role,
            title=validated_title,
            start_time=validated_start,
            end_time=validated_end,
            location=validated_location,
            meeting_url=validated_meeting_url,
            recruiter=validated_recruiter,
            gmail_url=(
                "https://mail.google.com/mail/u/0/#all/" + validated_message_id
            ),
            notes=validated_notes,
        )
        return {"success": True, "created": True, "interview": result}
