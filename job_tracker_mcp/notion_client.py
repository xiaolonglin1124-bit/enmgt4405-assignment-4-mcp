"""Minimal Notion REST API client for the job application data source."""

from typing import Any

import httpx

from .errors import ExternalServiceError


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2026-03-11"


class NotionJobClient:
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

    def create_application(
        self,
        *,
        company: str,
        role: str,
        job_url: str,
        status: str,
        applied_date: str,
        follow_up_date: str | None,
        notes: str,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "Role": {"title": [{"text": {"content": role}}]},
            "Company": {"rich_text": [{"text": {"content": company}}]},
            "Status": {"select": {"name": status}},
            "Applied Date": {"date": {"start": applied_date}},
            "Job URL": {"url": job_url},
            "Notes": {"rich_text": [{"text": {"content": notes}}]} if notes else {"rich_text": []},
        }
        if follow_up_date:
            properties["Follow-up Date"] = {"date": {"start": follow_up_date}}

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
            "company": company,
            "role": role,
            "status": status,
        }

    def list_applications(
        self,
        *,
        status: str,
        follow_up_before: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = []
        if status != "All":
            filters.append(
                {"property": "Status", "select": {"equals": status}}
            )
        if follow_up_before:
            filters.append(
                {
                    "property": "Follow-up Date",
                    "date": {"on_or_before": follow_up_before},
                }
            )

        payload: dict[str, Any] = {
            "page_size": limit,
            "sorts": [
                {"property": "Follow-up Date", "direction": "ascending"}
            ],
        }
        if len(filters) == 1:
            payload["filter"] = filters[0]
        elif filters:
            payload["filter"] = {"and": filters}

        # Endpoint and filter shape follow the official Query a Data Source API:
        # https://developers.notion.com/reference/query-a-data-source
        data = self._request(
            "POST",
            f"/data_sources/{self._data_source_id}/query",
            json=payload,
        )
        return [self._parse_page(page) for page in data.get("results", [])]

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            # Do not retain or re-emit response bodies, headers, local paths, or tokens.
            raise ExternalServiceError(
                "The external job application service is unavailable."
            ) from None

    @staticmethod
    def _parse_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties", {})
        return {
            "id": page.get("id", ""),
            "notion_url": page.get("url", ""),
            "role": _plain_text(properties.get("Role", {}).get("title", [])),
            "company": _plain_text(
                properties.get("Company", {}).get("rich_text", [])
            ),
            "status": (
                properties.get("Status", {}).get("select") or {}
            ).get("name", ""),
            "applied_date": _date_start(properties.get("Applied Date", {})),
            "follow_up_date": _date_start(properties.get("Follow-up Date", {})),
            "job_url": properties.get("Job URL", {}).get("url") or "",
            "notes": _plain_text(properties.get("Notes", {}).get("rich_text", [])),
        }


def _plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(str(item.get("plain_text", "")) for item in items)


def _date_start(prop: dict[str, Any]) -> str:
    return (prop.get("date") or {}).get("start", "")
