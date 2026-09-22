"""Read interview invitations from Gmail using a local OAuth token."""

from __future__ import annotations

import base64
import html
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from icalendar import Calendar

from .config import ConfigurationError
from .errors import ExternalServiceError

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
INTERVIEW_QUERY_TERMS = (
    '"interview" OR "phone screen" OR "technical screen" OR '
    '"onsite" OR "面试" OR "面談"'
)
_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SPACE_PATTERN = re.compile(r"\s+")


class GmailInterviewClient:
    """Small Gmail adapter that exposes only the data needed by this MCP server."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_token(cls, token_path: Path) -> GmailInterviewClient:
        """Build a read-only Gmail client from the locally stored OAuth token."""
        try:
            credentials = Credentials.from_authorized_user_file(
                token_path,
                [GMAIL_READONLY_SCOPE],
            )
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                token_path.write_text(credentials.to_json(), encoding="utf-8")
                token_path.chmod(0o600)
            if not credentials.valid:
                raise ConfigurationError(
                    "Gmail authorization is invalid. Run: python authorize_gmail.py"
                )
            return cls(
                build(
                    "gmail",
                    "v1",
                    credentials=credentials,
                    cache_discovery=False,
                )
            )
        except ConfigurationError:
            raise
        except (GoogleAuthError, OSError, ValueError) as exc:
            raise ConfigurationError(
                "Gmail authorization could not be loaded. Run: python authorize_gmail.py"
            ) from exc

    def list_weekly_interviews(
        self,
        *,
        week_start: datetime,
        week_end: datetime,
        lookback_days: int,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return calendar-backed interviews plus email candidates needing review."""
        after = int((datetime.now(week_start.tzinfo) - timedelta(days=lookback_days)).timestamp())
        query = f"after:{after} {{{INTERVIEW_QUERY_TERMS}}} -from:me"
        messages = self._list_messages(query=query, limit=limit)
        scheduled: list[dict[str, Any]] = []
        needs_review: list[dict[str, Any]] = []
        seen_events: set[str] = set()

        for message_stub in messages:
            message_id = str(message_stub.get("id", ""))
            if not message_id:
                continue
            message = self._get_message(message_id)
            parsed = parse_interview_message(
                message,
                timezone=week_start.tzinfo,
                attachment_loader=lambda attachment_id, mid=message_id: self._attachment(
                    mid, attachment_id
                ),
            )
            had_week_event = False
            for event in parsed["events"]:
                event_start = datetime.fromisoformat(event["start_time"])
                if not week_start <= event_start < week_end:
                    continue
                had_week_event = True
                key = str(event.get("uid") or f'{event["title"]}|{event["start_time"]}')
                if key in seen_events:
                    continue
                seen_events.add(key)
                if event["cancelled"]:
                    continue
                scheduled.append(event)

            received_at = datetime.fromisoformat(parsed["received_at"])
            if not had_week_event and week_start <= received_at < week_end:
                needs_review.append(parsed["candidate"])

        scheduled.sort(key=lambda item: item["start_time"])
        needs_review.sort(key=lambda item: item["received_at"], reverse=True)
        return {"scheduled": scheduled, "needs_review": needs_review}

    def _list_messages(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        page_token: str | None = None
        try:
            while len(messages) < limit:
                request = self._service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=min(100, limit - len(messages)),
                    pageToken=page_token,
                )
                data = request.execute()
                messages.extend(data.get("messages", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            return messages[:limit]
        except (HttpError, GoogleAuthError, OSError, ValueError):
            raise ExternalServiceError(
                "The external email service is unavailable."
            ) from None

    def _get_message(self, message_id: str) -> dict[str, Any]:
        try:
            return (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except (HttpError, GoogleAuthError, OSError, ValueError):
            raise ExternalServiceError(
                "The external email service is unavailable."
            ) from None

    def _attachment(self, message_id: str, attachment_id: str) -> str:
        try:
            result = (
                self._service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            return _decode_base64url(str(result.get("data", "")))
        except (HttpError, GoogleAuthError, OSError, ValueError):
            raise ExternalServiceError(
                "The external email service is unavailable."
            ) from None


def parse_interview_message(
    message: dict[str, Any],
    *,
    timezone: ZoneInfo,
    attachment_loader: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Parse safe metadata, excerpts, and iCalendar events from one Gmail message."""
    message_id = str(message.get("id", ""))
    payload = message.get("payload", {})
    headers = {
        str(item.get("name", "")).lower(): str(item.get("value", ""))
        for item in payload.get("headers", [])
    }
    subject = headers.get("subject", "(No subject)")
    sender = headers.get("from", "")
    received_at = _received_at(message, headers, timezone)
    text_parts: list[str] = []
    calendar_parts: list[str] = []

    for part in _walk_parts(payload):
        mime_type = str(part.get("mimeType", "")).lower()
        body = part.get("body", {})
        content = ""
        if body.get("data"):
            content = _decode_base64url(str(body["data"]))
        elif body.get("attachmentId") and attachment_loader:
            content = attachment_loader(str(body["attachmentId"]))

        if not content:
            continue
        filename = str(part.get("filename", "")).lower()
        if mime_type in {"text/calendar", "application/ics"} or filename.endswith(
            ".ics"
        ):
            calendar_parts.append(content)
        elif mime_type == "text/plain":
            text_parts.append(content)
        elif mime_type == "text/html" and not text_parts:
            text_parts.append(_TAG_PATTERN.sub(" ", html.unescape(content)))

    excerpt_source = " ".join(text_parts) or str(message.get("snippet", ""))
    excerpt = _SPACE_PATTERN.sub(" ", excerpt_source).strip()[:600]
    gmail_url = f"https://mail.google.com/mail/u/0/#all/{message_id}"
    events: list[dict[str, Any]] = []
    for calendar_text in calendar_parts:
        events.extend(
            _parse_calendar_events(
                calendar_text,
                timezone=timezone,
                message_id=message_id,
                gmail_url=gmail_url,
                subject=subject,
                sender=sender,
                excerpt=excerpt,
            )
        )

    return {
        "received_at": received_at.isoformat(),
        "events": events,
        "candidate": {
            "message_id": message_id,
            "subject": subject[:300],
            "sender": sender[:300],
            "received_at": received_at.isoformat(),
            "gmail_url": gmail_url,
            "excerpt": excerpt,
            "reason": "No calendar event was found; confirm the date and time manually.",
        },
    }


def _parse_calendar_events(
    calendar_text: str,
    *,
    timezone: ZoneInfo,
    message_id: str,
    gmail_url: str,
    subject: str,
    sender: str,
    excerpt: str,
) -> list[dict[str, Any]]:
    try:
        calendar = Calendar.from_ical(calendar_text)
    except (ValueError, TypeError):
        return []

    events: list[dict[str, Any]] = []
    for component in calendar.walk("VEVENT"):
        start_prop = component.get("dtstart")
        if start_prop is None:
            continue
        start = _calendar_datetime(start_prop.dt, timezone)
        end_prop = component.get("dtend")
        end = (
            _calendar_datetime(end_prop.dt, timezone)
            if end_prop is not None
            else start + timedelta(hours=1)
        )
        title = _calendar_text(component.get("summary")) or subject
        location = _calendar_text(component.get("location"))
        description = _calendar_text(component.get("description"))
        organizer = _calendar_text(component.get("organizer")).removeprefix("mailto:")
        status = _calendar_text(component.get("status")).upper()
        method = _calendar_text(calendar.get("method")).upper()
        meeting_url = _first_meeting_url(f"{location} {description}")
        events.append(
            {
                "message_id": message_id,
                "uid": _calendar_text(component.get("uid")),
                "title": title[:300],
                "start_time": start.astimezone(timezone).isoformat(),
                "end_time": end.astimezone(timezone).isoformat(),
                "timezone": str(timezone),
                "location": location[:500],
                "meeting_url": meeting_url,
                "organizer": organizer[:300] or sender[:300],
                "subject": subject[:300],
                "gmail_url": gmail_url,
                "excerpt": excerpt,
                "cancelled": status == "CANCELLED" or method == "CANCEL",
            }
        )
    return events


def _walk_parts(part: dict[str, Any]) -> list[dict[str, Any]]:
    result = [part]
    for child in part.get("parts", []):
        result.extend(_walk_parts(child))
    return result


def _decode_base64url(value: str) -> str:
    if not value:
        return ""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8", errors="replace")


def _received_at(
    message: dict[str, Any], headers: dict[str, str], timezone: ZoneInfo
) -> datetime:
    internal = message.get("internalDate")
    if internal:
        try:
            return datetime.fromtimestamp(int(str(internal)) / 1000, tz=timezone)
        except (TypeError, ValueError, OverflowError):
            pass
    try:
        parsed = parsedate_to_datetime(headers.get("date", ""))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone)
        return parsed.astimezone(timezone)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone)


def _calendar_datetime(value: datetime | date, timezone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone) if value.tzinfo is None else value
    return datetime.combine(value, time.min, tzinfo=timezone)


def _calendar_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _first_meeting_url(value: str) -> str:
    urls = [match.rstrip(".,);]") for match in _URL_PATTERN.findall(value)]
    preferred = (
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "webex.com",
    )
    for domain in preferred:
        for url in urls:
            if domain in url.lower():
                return url[:2048]
    return urls[0][:2048] if urls else ""
