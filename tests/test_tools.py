from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter
from job_tracker_mcp.service import InterviewScheduleService

from .fakes import FakeGmailClient, FakeNotionClient


def make_service() -> tuple[
    InterviewScheduleService, FakeGmailClient, FakeNotionClient
]:
    gmail = FakeGmailClient()
    notion = FakeNotionClient()
    limiter = SlidingWindowRateLimiter(max_calls=20, window_seconds=60)
    return InterviewScheduleService(gmail, notion, limiter), gmail, notion


def test_list_weekly_invites_uses_monday_boundary() -> None:
    service, gmail, _ = make_service()
    gmail.result["scheduled"] = [
        {"title": "Product interview", "start_time": "2026-09-23T10:00:00-04:00"}
    ]

    result = service.list_weekly_interview_invites(
        week_start="2026-09-23",
        timezone="America/New_York",
        lookback_days=90,
        limit=20,
    )

    assert result["success"] is True
    assert result["week_start"] == "2026-09-21"
    assert result["week_end_exclusive"] == "2026-09-28"
    assert result["scheduled_count"] == 1
    assert gmail.calls[0]["week_start"].isoformat() == "2026-09-21T00:00:00-04:00"


def test_add_interview_validates_and_creates_notion_row() -> None:
    service, _, notion = make_service()

    result = service.add_interview_to_notion(
        message_id="18abc123",
        company=" Adobe ",
        role="Product Designer",
        title="Portfolio Interview",
        start_time="2026-09-23T10:00:00-04:00",
        end_time="2026-09-23T11:00:00-04:00",
        meeting_url="https://meet.google.com/abc-defg-hij",
    )

    assert result["success"] is True
    assert result["created"] is True
    assert notion.created[0]["company"] == "Adobe"
    assert notion.created[0]["gmail_url"].endswith("18abc123")


def test_add_interview_is_idempotent_by_gmail_message_id() -> None:
    service, _, notion = make_service()
    notion.existing = {"id": "existing", "url": "https://notion.so/existing"}

    result = service.add_interview_to_notion(
        message_id="18abc123",
        company="Adobe",
        role="Product Designer",
        start_time="2026-09-23T10:00:00-04:00",
    )

    assert result["created"] is False
    assert notion.created == []
