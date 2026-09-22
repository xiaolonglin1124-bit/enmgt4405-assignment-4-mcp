import pytest

from job_tracker_mcp.errors import ValidationError
from job_tracker_mcp.validators import (
    validate_datetime_range,
    validate_optional_url,
    validate_timezone,
)


def test_javascript_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_optional_url("javascript:alert('xss')", "meeting_url")


def test_datetime_without_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_datetime_range("2026-09-23T10:00:00", None)


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_datetime_range(
            "2026-09-23T10:00:00-04:00",
            "2026-09-23T09:00:00-04:00",
        )


def test_invalid_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_timezone("Mars/Olympus")
