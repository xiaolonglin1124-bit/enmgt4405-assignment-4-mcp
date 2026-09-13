"""Test doubles shared by unit tests."""

from typing import Any


class FakeNotionClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []
        self.list_result: list[dict[str, Any]] = []

    def create_application(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        return {
            "id": "page-123",
            "url": "https://notion.so/page-123",
            "company": kwargs["company"],
            "role": kwargs["role"],
            "status": kwargs["status"],
        }

    def list_applications(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.list_calls.append(kwargs)
        return self.list_result
