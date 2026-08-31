class ProfileFetchError(Exception):
    """Base exception for profile fetching."""


class ProfileNotFoundError(ProfileFetchError):
    """Raised when the requested profile does not exist."""


class PrivateProfileError(ProfileFetchError):
    """Raised when a profile is private."""


class RateLimitError(ProfileFetchError):
    """Raised when Instagram rate-limits requests."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)

        self.retry_after_seconds = retry_after_seconds


class CrawlSessionStoppedError(ProfileFetchError):
    """
    Raised when the crawl session is stopped
    after repeated rate limits.
    """
