import pytest

from job_tracker_mcp.errors import ValidationError
from job_tracker_mcp.validators import validate_status, validate_url


def test_javascript_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_url("javascript:alert('xss')")


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_status("Maybe")
