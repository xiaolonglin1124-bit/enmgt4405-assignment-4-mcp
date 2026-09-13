from job_tracker_mcp.server import _safe_tool_call


def test_unexpected_exception_does_not_disclose_sensitive_details() -> None:
    fake_token = "secret_test_token_123"
    fake_path = "/Users/student/private/server.py"

    def malicious_failure() -> dict[str, object]:
        raise RuntimeError(
            f"Authorization: Bearer {fake_token}; traceback file={fake_path}"
        )

    result = _safe_tool_call(malicious_failure)
    rendered = str(result)

    assert result["error_code"] == "INTERNAL_ERROR"
    assert fake_token not in rendered
    assert fake_path not in rendered
    assert "Authorization" not in rendered
    assert "Traceback" not in rendered
