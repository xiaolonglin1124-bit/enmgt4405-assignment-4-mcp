"""Test doubles shared by unit tests."""

from typing import Any


class FakeGmailClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result: dict[str, list[dict[str, Any]]] = {
            "scheduled": [],
            "needs_review": [],
        }

    def list_weekly_interviews(self, **kwargs: Any) -> dict[str, list[dict[str, Any]]]:
        self.calls.append(kwargs)
        return self.result


class FakeNotionClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.existing: dict[str, Any] | None = None
        self.lookup_ids: list[str] = []

    def find_by_gmail_message_id(self, message_id: str) -> dict[str, Any] | None:
        self.lookup_ids.append(message_id)
        return self.existing

    def create_interview(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        return {
            "id": "page-123",
            "url": "https://notion.so/page-123",
            "title": kwargs["title"],
            "company": kwargs["company"],
            "role": kwargs["role"],
            "start_time": kwargs["start_time"],
        }
