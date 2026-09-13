from job_tracker_mcp.rate_limiter import SlidingWindowRateLimiter
from job_tracker_mcp.service import JobApplicationService

from .fakes import FakeNotionClient


def make_service() -> tuple[JobApplicationService, FakeNotionClient]:
    notion = FakeNotionClient()
    limiter = SlidingWindowRateLimiter(max_calls=20, window_seconds=60)
    return JobApplicationService(notion, limiter), notion


def test_add_job_application_validates_and_creates_record() -> None:
    service, notion = make_service()

    result = service.add_job_application(
        company=" Adobe ",
        role="Product Designer",
        job_url="https://careers.example.com/jobs/123",
        applied_date="2026-09-13",
        follow_up_date="2026-09-20",
        notes="Applied through the company website.",
    )

    assert result["success"] is True
    assert notion.created[0]["company"] == "Adobe"
    assert notion.created[0]["status"] == "Applied"


def test_list_job_applications_passes_filters() -> None:
    service, notion = make_service()
    notion.list_result = [{"company": "Adobe", "status": "Interview"}]

    result = service.list_job_applications(
        status="interview",
        follow_up_before="2026-09-30",
        limit=10,
    )

    assert result["count"] == 1
    assert notion.list_calls == [
        {
            "status": "Interview",
            "follow_up_before": "2026-09-30",
            "limit": 10,
        }
    ]
