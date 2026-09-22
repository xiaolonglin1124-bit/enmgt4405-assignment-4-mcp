from gmail_interview_scheduler_mcp.rate_limiter import SlidingWindowRateLimiter
from gmail_interview_scheduler_mcp.server import _safe_tool_call
from gmail_interview_scheduler_mcp.service import InterviewScheduleService

from .fakes import FakeGmailClient, FakeNotionClient


def test_sixth_call_is_blocked_before_gmail_access() -> None:
    now = 100.0
    limiter = SlidingWindowRateLimiter(
        max_calls=5,
        window_seconds=60,
        clock=lambda: now,
    )
    gmail = FakeGmailClient()
    service = InterviewScheduleService(gmail, FakeNotionClient(), limiter)

    for _ in range(5):
        result = _safe_tool_call(
            lambda: service.list_weekly_interview_invites(
                week_start="2026-09-21"
            )
        )
        assert result["success"] is True

    blocked = _safe_tool_call(
        lambda: service.list_weekly_interview_invites(week_start="2026-09-21")
    )

    assert blocked["success"] is False
    assert blocked["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert blocked["retry_after_seconds"] == 61
    assert len(gmail.calls) == 5


def test_calls_are_allowed_again_after_window() -> None:
    current = [100.0]
    limiter = SlidingWindowRateLimiter(1, 60, clock=lambda: current[0])
    limiter.check("tool")

    current[0] = 161.0
    limiter.check("tool")
