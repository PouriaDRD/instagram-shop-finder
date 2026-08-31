from dataclasses import dataclass, field

from app.crawler.exceptions import (
    CrawlSessionStoppedError,
)


@dataclass(slots=True)
class RateLimitPolicy:
    """Conservative rate-limiting policy for tracking consecutive Instagram HTTP 429 errors.

    Calculates progressive cooldown delays based on configured intervals and terminates
    the crawling session once a specified threshold of consecutive rate limits is met.

    Attributes:
        cooldown_seconds: Sequence of backoff delays in seconds applied per consecutive rate limit.
        max_consecutive_rate_limits: Maximum allowed consecutive rate limits before halting the session.
    """

    cooldown_seconds: tuple[
        float,
        ...,
    ] = (
        30.0,
        120.0,
    )

    max_consecutive_rate_limits: int = 3

    # Internal state counter tracking consecutive rate limit occurrences
    _consecutive_rate_limits: int = field(
        default=0,
        init=False,
    )

    @property
    def consecutive_rate_limits(self) -> int:
        """Retrieves the current count of consecutive rate limit occurrences."""
        return self._consecutive_rate_limits

    def register_success(
        self,
    ) -> None:
        """Resets the consecutive rate limit counter to zero upon a successful request."""
        self._consecutive_rate_limits = 0

    def register_rate_limit(
        self,
        *,
        retry_after_seconds: float | None = None,
    ) -> float:
        """Registers a rate limit occurrence, updates internal counters, and calculates cooldown.

        Args:
            retry_after_seconds: Optional delay extracted from HTTP Retry-After response headers.

        Returns:
            The computed delay duration in seconds to pause before retrying.

        Raises:
            CrawlSessionStoppedError: If consecutive rate limits reach or exceed max_consecutive_rate_limits.
        """
        self._consecutive_rate_limits += 1

        # Terminate crawl session if the consecutive failure threshold is reached
        if self._consecutive_rate_limits >= self.max_consecutive_rate_limits:
            raise CrawlSessionStoppedError(
                "Crawl session stopped after "
                f"{self._consecutive_rate_limits} "
                "consecutive Instagram rate limits."
            )

        policy_delay = self._get_policy_delay()

        if retry_after_seconds is None or retry_after_seconds <= 0:
            return policy_delay

        # Ensure cooldown duration honors the maximum between policy default and Retry-After header
        return max(
            policy_delay,
            retry_after_seconds,
        )

    def _get_policy_delay(self) -> float:
        """Determines the appropriate backoff delay duration according to the configured schedule.

        Returns:
            The delay in seconds corresponding to the current consecutive rate limit count.
            Returns the last element if the count exceeds the tuple length, or 0.0 if empty.
        """
        index = self._consecutive_rate_limits - 1

        if not self.cooldown_seconds:
            return 0.0

        # Cap backoff index to the last element if counter exceeds configured schedule
        if index >= len(self.cooldown_seconds):
            return self.cooldown_seconds[-1]

        return self.cooldown_seconds[index]
