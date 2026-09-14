"""Validation helpers for tool inputs."""

import re
from datetime import date
from urllib.parse import urlparse

from .errors import ValidationError

ALLOWED_STATUSES = (
    "Wishlist",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_text(value: str, field: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field} is required.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters.")
    if _CONTROL_CHARACTERS.search(cleaned):
        raise ValidationError(f"{field} contains unsupported control characters.")
    return cleaned


def validate_optional_text(value: str, field: str, max_length: int) -> str:
    if not value:
        return ""
    return validate_text(value, field, max_length)


def validate_iso_date(value: str, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must use YYYY-MM-DD format.") from exc


def validate_optional_date(value: str | None, field: str) -> str | None:
    if value is None or not value.strip():
        return None
    return validate_iso_date(value.strip(), field)


def validate_url(value: str) -> str:
    cleaned = validate_text(value, "job_url", 2048)
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("job_url must be a valid HTTP or HTTPS URL.")
    return cleaned


def validate_status(value: str, allow_all: bool = False) -> str:
    cleaned = value.strip().title()
    valid = (*ALLOWED_STATUSES, "All") if allow_all else ALLOWED_STATUSES
    if cleaned not in valid:
        choices = ", ".join(valid)
        raise ValidationError(f"status must be one of: {choices}.")
    return cleaned


def validate_limit(value: int) -> int:
    if not 1 <= value <= 50:
        raise ValidationError("limit must be between 1 and 50.")
    return value
