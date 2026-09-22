"""Minimal Notion REST API client for the interview schedule data source."""

from typing import Any

import httpx

from .errors import ExternalServiceError

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2026-03-11"


class NotionScheduleClient:
    def __init__(
        self,
        token: str,
        data_source_id: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._data_source_id = data_source_id
        self._client = httpx.Client(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=10.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def find_by_gmail_message_id(self, message_id: str) -> dict[str, Any] | None:
        payload = {
            "page_size": 1,
            "filter": {
                "property": "Gmail Message ID",
                "rich_text": {"equals": message_id},
            },
        }
        # Endpoint and filter shape follow the official Query a Data Source API:
        # https://developers.notion.com/reference/query-a-data-source
        data = self._request(
            "POST",
            f"/data_sources/{self._data_source_id}/query",
            json=payload,
        )
        results = data.get("results", [])
        if not results:
            return None
        return {
            "id": results[0].get("id", ""),
            "url": results[0].get("url", ""),
        }

    def create_interview(
        self,
        *,
        message_id: str,
        company: str,
        role: str,
        title: str,
        start_time: str,
        end_time: str | None,
        location: str,
        meeting_url: str,
        recruiter: str,
        gmail_url: str,
        notes: str,
    ) -> dict[str, Any]:
        date_value: dict[str, Any] = {"start": start_time}
        if end_time:
            date_value["end"] = end_time

        properties: dict[str, Any] = {
            "Interview": {"title": [_text(title)]},
            "Company": {"rich_text": [_text(company)]},
            "Role": {"rich_text": [_text(role)]},
            "Time": {"date": date_value},
            "Status": {"select": {"name": "Scheduled"}},
            "Location": {"rich_text": [_text(location)]} if location else {"rich_text": []},
            "Meeting URL": {"url": meeting_url or None},
            "Recruiter": {"rich_text": [_text(recruiter)]}
            if recruiter
            else {"rich_text": []},
            "Gmail URL": {"url": gmail_url},
            "Gmail Message ID": {"rich_text": [_text(message_id)]},
            "Notes": {"rich_text": [_text(notes)]} if notes else {"rich_text": []},
        }
        payload = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self._data_source_id,
            },
            "properties": properties,
        }

        # Endpoint and payload shape follow the official Notion Create a Page API:
        # https://developers.notion.com/reference/post-page
        data = self._request("POST", "/pages", json=payload)
        return {
            "id": data.get("id", ""),
            "url": data.get("url", ""),
            "title": title,
            "company": company,
            "role": role,
            "start_time": start_time,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            # Never retain or re-emit response bodies, headers, paths, or tokens.
            raise ExternalServiceError(
                "The external schedule service is unavailable."
            ) from None


def _text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": {"content": value}}
