import pytest

from job_tracker_mcp.errors import RateLimitExceeded
from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter


def test_sixth_call_is_blocked_in_demo_configuration() -> None:
    now = 100.0
    limiter = SlidingWindowRateLimiter(
        max_calls=5,
        window_seconds=60,
        clock=lambda: now,
    )

    for _ in range(5):
        limiter.check("list_job_applications")

    with pytest.raises(RateLimitExceeded) as blocked:
        limiter.check("list_job_applications")

    assert blocked.value.retry_after_seconds == 61


def test_calls_are_allowed_again_after_window() -> None:
    current = [100.0]
    limiter = SlidingWindowRateLimiter(1, 60, clock=lambda: current[0])
    limiter.check("tool")

    current[0] = 161.0
    limiter.check("tool")
