from pathlib import Path

import pytest

from job_tracker_mcp.config import ConfigurationError, load_settings


def test_settings_require_dedicated_interview_data_source(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "NOTION_TOKEN=secret_test",
                "NOTION_DATA_SOURCE_ID=legacy-job-table",
                f"GMAIL_TOKEN_PATH={token_path}",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_settings(env_path)


def test_settings_load_local_oauth_and_notion_paths(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "NOTION_TOKEN=secret_test",
                "NOTION_INTERVIEW_DATA_SOURCE_ID=interview-table",
                f"GMAIL_TOKEN_PATH={token_path}",
            )
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_path)

    assert settings.notion_interview_data_source_id == "interview-table"
    assert settings.gmail_token_path == token_path
