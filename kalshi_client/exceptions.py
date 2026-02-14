"""Custom exceptions for the Kalshi client."""


class KalshiError(Exception):
    """Base exception for all Kalshi errors."""
    pass


class KalshiAuthError(KalshiError):
    """Raised when authentication fails."""
    pass


class KalshiAPIError(KalshiError):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str, response_body: dict | None = None):
        self.status_code = status_code
        self.response_body = response_body or {}
        super().__init__(f"HTTP {status_code}: {message}")


class KalshiRateLimitError(KalshiAPIError):
    """Raised when rate limited by the API."""

    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(429, "Rate limit exceeded", {})
