import json

import httpx
import pytest

from gmail_interview_scheduler_mcp.errors import ExternalServiceError
from gmail_interview_scheduler_mcp.notion_client import (
    NOTION_API_VERSION,
    NotionScheduleClient,
)


def test_create_interview_builds_expected_notion_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["Authorization"]
        captured["version"] = request.headers["Notion-Version"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": "page-123", "url": "https://notion.so/page-123"},
        )

    client = NotionScheduleClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.create_interview(
            message_id="18abc123",
            company="Adobe",
            role="Product Designer",
            title="Portfolio Interview",
            start_time="2026-09-23T10:00:00-04:00",
            end_time="2026-09-23T11:00:00-04:00",
            location="Remote",
            meeting_url="https://meet.google.com/abc-defg-hij",
            recruiter="recruiter@example.com",
            gmail_url="https://mail.google.com/mail/u/0/#all/18abc123",
            notes="Prepare portfolio",
        )
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/pages"
    assert captured["authorization"] == "Bearer test-token"
    assert captured["version"] == NOTION_API_VERSION
    assert body["parent"] == {
        "type": "data_source_id",
        "data_source_id": "data-source-123",
    }
    assert body["properties"]["Interview"]["title"][0]["text"]["content"] == (
        "Portfolio Interview"
    )
    assert body["properties"]["Time"]["date"]["end"].endswith("-04:00")
    assert result["id"] == "page-123"


def test_duplicate_lookup_uses_gmail_message_id_filter() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"results": [{"id": "existing", "url": "https://notion.so/x"}]},
        )

    client = NotionScheduleClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.find_by_gmail_message_id("18abc123")
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    assert captured["path"] == "/v1/data_sources/data-source-123/query"
    assert body["filter"]["rich_text"]["equals"] == "18abc123"
    assert result == {"id": "existing", "url": "https://notion.so/x"}


def test_notion_error_body_is_not_disclosed() -> None:
    fake_secret = "secret_should_never_escape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"message": f"Invalid bearer token: {fake_secret}"},
            request=request,
        )

    client = NotionScheduleClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ExternalServiceError) as caught:
            client.find_by_gmail_message_id("18abc123")
    finally:
        client.close()

    assert fake_secret not in str(caught.value)
    assert "401" not in str(caught.value)
