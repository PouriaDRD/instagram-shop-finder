import time
from collections.abc import Callable

from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    RateLimitError,
)
from app.crawler.playwright_scraper import (
    InstagramPlaywrightProfileFetcher,
)
from app.crawler.rate_limit import (
    RateLimitPolicy,
)
from app.models.raw_profile import (
    RawProfileData,
)


class InstagramCrawlSession:
    """
    Persistent Instagram crawling session.

    Responsibilities:
    - reuse one Playwright browser/context
    - handle HTTP 429 conservatively
    - apply cooldown between retries
    - stop after repeated rate limits
    """

    def __init__(
        self,
        *,
        fetcher: InstagramPlaywrightProfileFetcher | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        sleeper: Callable[
            [float],
            None,
        ] = time.sleep,
    ) -> None:
        self._fetcher = fetcher or InstagramPlaywrightProfileFetcher()

        self._rate_limit_policy = rate_limit_policy or RateLimitPolicy()

        self._sleeper = sleeper

        self._is_open = False
        self._is_stopped = False

    @property
    def is_open(
        self,
    ) -> bool:
        return self._is_open

    @property
    def is_stopped(
        self,
    ) -> bool:
        return self._is_stopped

    @property
    def consecutive_rate_limits(
        self,
    ) -> int:
        return self._rate_limit_policy.consecutive_rate_limits

    def open(
        self,
    ) -> None:
        if self._is_open:
            return

        if self._is_stopped:
            raise CrawlSessionStoppedError("Crawl session has already " "been stopped.")

        self._fetcher.open()
        self._is_open = True

    def close(
        self,
    ) -> None:
        if not self._is_open:
            return

        self._fetcher.close()
        self._is_open = False

    def fetch(
        self,
        username: str,
    ) -> RawProfileData:
        if self._is_stopped:
            raise CrawlSessionStoppedError("Crawl session has been stopped.")

        if not self._is_open:
            self.open()

        while True:
            try:
                profile = self._fetcher.fetch(username)

            except RateLimitError as exc:
                try:
                    delay = self._rate_limit_policy.register_rate_limit(
                        retry_after_seconds=(exc.retry_after_seconds),
                    )

                except CrawlSessionStoppedError:
                    self._is_stopped = True
                    self.close()
                    raise

                self._sleeper(delay)

                continue

            self._rate_limit_policy.register_success()

            return profile

    def __enter__(
        self,
    ) -> "InstagramCrawlSession":
        self.open()

        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
