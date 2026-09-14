import json

import httpx
import pytest

from job_tracker_mcp.errors import ExternalServiceError
from job_tracker_mcp.notion_client import NOTION_API_VERSION, NotionJobClient


def test_create_application_builds_expected_notion_request() -> None:
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

    client = NotionJobClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.create_application(
            company="Adobe",
            role="Product Designer",
            job_url="https://example.com/jobs/123",
            status="Applied",
            applied_date="2026-09-13",
            follow_up_date="2026-09-20",
            notes="Portfolio submitted",
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
    assert body["properties"]["Role"]["title"][0]["text"]["content"] == (
        "Product Designer"
    )
    assert result["id"] == "page-123"


def test_list_applications_builds_filters_and_parses_result() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "page-456",
                        "url": "https://notion.so/page-456",
                        "properties": {
                            "Role": {"title": [{"plain_text": "Engineer"}]},
                            "Company": {"rich_text": [{"plain_text": "Example Corp"}]},
                            "Status": {"select": {"name": "Interview"}},
                            "Applied Date": {"date": {"start": "2026-09-01"}},
                            "Follow-up Date": {"date": {"start": "2026-09-15"}},
                            "Job URL": {"url": "https://example.com/job"},
                            "Notes": {"rich_text": [{"plain_text": "Phone screen"}]},
                        },
                    }
                ]
            },
        )

    client = NotionJobClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        results = client.list_applications(
            status="Interview",
            follow_up_before="2026-09-30",
            limit=10,
        )
    finally:
        client.close()

    body = captured["body"]
    assert isinstance(body, dict)
    assert captured["path"] == "/v1/data_sources/data-source-123/query"
    assert body["filter"]["and"][0] == {
        "property": "Status",
        "select": {"equals": "Interview"},
    }
    assert results[0]["company"] == "Example Corp"
    assert results[0]["follow_up_date"] == "2026-09-15"


def test_notion_error_body_is_not_disclosed() -> None:
    fake_secret = "secret_should_never_escape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"message": f"Invalid bearer token: {fake_secret}"},
            request=request,
        )

    client = NotionJobClient(
        "test-token",
        "data-source-123",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ExternalServiceError) as caught:
            client.list_applications(status="All", follow_up_before=None, limit=10)
    finally:
        client.close()

    assert fake_secret not in str(caught.value)
    assert "401" not in str(caught.value)
