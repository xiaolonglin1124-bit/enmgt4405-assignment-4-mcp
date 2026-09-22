import base64
from datetime import datetime
from zoneinfo import ZoneInfo

from job_tracker_mcp.gmail_client import GmailInterviewClient, parse_interview_message


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def test_calendar_invite_is_parsed_without_returning_full_email() -> None:
    calendar = """BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VEVENT
UID:interview-123@example.com
DTSTART:20260923T140000Z
DTEND:20260923T150000Z
SUMMARY:Adobe Product Designer Interview
LOCATION:https://meet.google.com/abc-defg-hij
ORGANIZER:mailto:recruiter@example.com
DESCRIPTION:Please join the portfolio interview.
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""
    message = {
        "id": "18abc123",
        "internalDate": "1790168400000",
        "snippet": "Private full email content should be shortened",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Interview invitation"},
                {"name": "From", "value": "Recruiter <recruiter@example.com>"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded("See you soon")}},
                {"mimeType": "text/calendar", "body": {"data": encoded(calendar)}},
            ],
        },
    }

    parsed = parse_interview_message(
        message,
        timezone=ZoneInfo("America/New_York"),
    )

    event = parsed["events"][0]
    assert event["title"] == "Adobe Product Designer Interview"
    assert event["start_time"] == "2026-09-23T10:00:00-04:00"
    assert event["meeting_url"] == "https://meet.google.com/abc-defg-hij"
    assert event["cancelled"] is False
    assert parsed["candidate"]["excerpt"] == "See you soon"


def test_calendar_attachment_can_be_loaded_by_id() -> None:
    calendar = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:x
DTSTART:20260924T140000Z
SUMMARY:Technical Interview
END:VEVENT
END:VCALENDAR
"""
    message = {
        "id": "msg",
        "internalDate": "1790254800000",
        "payload": {
            "headers": [{"name": "Subject", "value": "Technical Interview"}],
            "parts": [
                {
                    "mimeType": "text/calendar",
                    "body": {"attachmentId": "attachment-1"},
                }
            ],
        },
    }

    parsed = parse_interview_message(
        message,
        timezone=ZoneInfo("America/New_York"),
        attachment_loader=lambda attachment_id: calendar
        if attachment_id == "attachment-1"
        else "",
    )

    assert parsed["events"][0]["end_time"] == "2026-09-24T11:00:00-04:00"


def test_newer_cancellation_suppresses_older_invitation() -> None:
    def message(message_id: str, method: str, internal_date: str) -> dict[str, object]:
        calendar = f"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:{method}
BEGIN:VEVENT
UID:same-event@example.com
DTSTART:20260924T140000Z
DTEND:20260924T150000Z
SUMMARY:Technical Interview
STATUS:{"CANCELLED" if method == "CANCEL" else "CONFIRMED"}
END:VEVENT
END:VCALENDAR
"""
        return {
            "id": message_id,
            "internalDate": internal_date,
            "payload": {
                "headers": [{"name": "Subject", "value": "Technical Interview"}],
                "parts": [
                    {"mimeType": "text/calendar", "body": {"data": encoded(calendar)}}
                ],
            },
        }

    messages_by_id = {
        "new-cancel": message("new-cancel", "CANCEL", "1790254800000"),
        "old-request": message("old-request", "REQUEST", "1790168400000"),
    }

    class Request:
        def __init__(self, result: dict[str, object]) -> None:
            self.result = result

        def execute(self) -> dict[str, object]:
            return self.result

    class Messages:
        def list(self, **kwargs: object) -> Request:
            return Request(
                {"messages": [{"id": "new-cancel"}, {"id": "old-request"}]}
            )

        def get(self, **kwargs: object) -> Request:
            return Request(messages_by_id[str(kwargs["id"])])

    class Users:
        def messages(self) -> Messages:
            return Messages()

    class Service:
        def users(self) -> Users:
            return Users()

    zone = ZoneInfo("America/New_York")
    result = GmailInterviewClient(Service()).list_weekly_interviews(
        week_start=datetime(2026, 9, 21, tzinfo=zone),
        week_end=datetime(2026, 9, 28, tzinfo=zone),
        lookback_days=90,
        limit=50,
    )

    assert result["scheduled"] == []
    assert result["needs_review"] == []
