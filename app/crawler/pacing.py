from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class CrawlPacingPolicy:
    """Conservative pacing policy for public Instagram profile requests.

    This policy intentionally slows crawling down to reduce request
    frequency and respect service-side rate limits.

    It is not intended to bypass access controls or hide automation.
    """

    delay_between_requests_seconds: float = 12.0

    requests_per_batch: int = 6

    batch_cooldown_seconds: float = 40.0

    def __post_init__(
        self,
    ) -> None:
        if self.delay_between_requests_seconds < 0:
            raise ValueError("delay_between_requests_seconds " "cannot be negative.")

        if self.requests_per_batch <= 0:
            raise ValueError("requests_per_batch must " "be greater than zero.")

        if self.batch_cooldown_seconds < 0:
            raise ValueError("batch_cooldown_seconds " "cannot be negative.")

    def delay_before_request(
        self,
        *,
        request_number: int,
    ) -> float:
        """Return required delay before a request.

        request_number is 1-based.
        """

        if request_number <= 1:
            return 0.0

        delay = self.delay_between_requests_seconds

        previous_request_number = request_number - 1

        if previous_request_number % self.requests_per_batch == 0:
            delay += self.batch_cooldown_seconds

        return delay
