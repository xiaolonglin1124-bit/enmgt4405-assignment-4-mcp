"""Configuration loaded directly from a local .env file."""

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(Exception):
    """Raised when required local configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_data_source_id: str
    rate_limit_calls: int = 5
    rate_limit_window_seconds: int = 60


def load_settings(env_path: Path | None = None) -> Settings:
    """Read secrets from .env without copying them into process environment variables."""
    path = env_path or PROJECT_ROOT / ".env"
    values = dotenv_values(path)

    token = (values.get("NOTION_TOKEN") or "").strip()
    data_source_id = (values.get("NOTION_DATA_SOURCE_ID") or "").strip()

    if not token or not data_source_id:
        raise ConfigurationError(
            "Create .env from .env.example and provide the Notion credentials."
        )

    try:
        calls = int(values.get("MCP_RATE_LIMIT_CALLS") or "5")
        window = int(values.get("MCP_RATE_LIMIT_WINDOW_SECONDS") or "60")
    except ValueError as exc:
        raise ConfigurationError("Rate-limit settings must be integers.") from exc

    if calls < 1 or window < 1:
        raise ConfigurationError("Rate-limit settings must be positive integers.")

    return Settings(
        notion_token=token,
        notion_data_source_id=data_source_id,
        rate_limit_calls=calls,
        rate_limit_window_seconds=window,
    )
