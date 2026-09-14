from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter
from job_tracker_mcp.server import _safe_tool_call
from job_tracker_mcp.service import JobApplicationService

from .fakes import FakeNotionClient


def test_sixth_call_is_blocked_in_demo_configuration() -> None:
    now = 100.0
    limiter = SlidingWindowRateLimiter(
        max_calls=5,
        window_seconds=60,
        clock=lambda: now,
    )
    notion = FakeNotionClient()
    service = JobApplicationService(notion, limiter)

    for _ in range(5):
        result = _safe_tool_call(service.list_job_applications)
        assert result["success"] is True

    blocked = _safe_tool_call(service.list_job_applications)

    assert blocked["success"] is False
    assert blocked["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert blocked["retry_after_seconds"] == 61
    assert len(notion.list_calls) == 5


def test_calls_are_allowed_again_after_window() -> None:
    current = [100.0]
    limiter = SlidingWindowRateLimiter(1, 60, clock=lambda: current[0])
    limiter.check("tool")

    current[0] = 161.0
    limiter.check("tool")
