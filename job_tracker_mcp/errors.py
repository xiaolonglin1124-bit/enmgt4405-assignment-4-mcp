"""Internal exceptions with deliberately non-sensitive public messages."""


class ValidationError(Exception):
    """Raised when a tool argument is invalid."""


class RateLimitExceeded(Exception):
    """Raised when a local tool-call limit is exceeded."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__("Local rate limit exceeded")


class ExternalServiceError(Exception):
    """Raised for Notion failures without retaining sensitive response details."""
