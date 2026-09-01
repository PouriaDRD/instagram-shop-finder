from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    RateLimitError,
)
from app.crawler.pacing import (
    CrawlPacingPolicy,
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


class ProfileFetcherProtocol(Protocol):
    def open(
        self,
    ) -> None: ...

    def fetch(
        self,
        username: str,
    ) -> RawProfileData: ...

    def close(
        self,
    ) -> None: ...


class InstagramCrawlSession:
    """Managed Instagram public-profile crawl session.

    Responsibilities:
    - open/close the underlying fetcher
    - conservative pacing between distinct profile checks
    - periodic batch cooldowns
    - rate-limit retry/backoff
    - crawl-session safety stop

    Important:
    Pacing is applied between separate profile fetch operations,
    not between retries for the same profile.

    Rate-limit retries are controlled exclusively by RateLimitPolicy.
    """

    def __init__(
        self,
        *,
        fetcher: ProfileFetcherProtocol | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        pacing_policy: CrawlPacingPolicy | None = None,
        sleeper: Callable[
            [float],
            None,
        ] = time.sleep,
    ) -> None:
        self._fetcher = fetcher or InstagramPlaywrightProfileFetcher()

        self._rate_limit_policy = rate_limit_policy or RateLimitPolicy()

        self._pacing_policy = pacing_policy or CrawlPacingPolicy()

        self._sleeper = sleeper

        self._is_stopped = False

        self._is_open = False

        # Number of distinct profile fetch() calls that
        # have actually started.
        #
        # Retries caused by RateLimitError do NOT increase
        # this counter.
        self._profile_request_count = 0

    @property
    def is_stopped(
        self,
    ) -> bool:
        return self._is_stopped

    @property
    def request_count(
        self,
    ) -> int:
        return self._profile_request_count

    def __enter__(
        self,
    ) -> InstagramCrawlSession:
        self.open()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

    def open(
        self,
    ) -> None:
        """Open the underlying browser/fetcher once."""

        if self._is_open:
            return

        open_method = getattr(
            self._fetcher,
            "open",
            None,
        )

        if callable(open_method):
            open_method()

        self._is_open = True

    def _wait_before_profile(
        self,
    ) -> None:
        """Apply pacing before a new distinct profile check.

        The very first profile starts immediately.

        Retries for the same profile never call this method again.
        """

        next_profile_number = self._profile_request_count + 1

        delay = self._pacing_policy.delay_before_request(
            request_number=(next_profile_number),
        )

        if delay <= 0:
            return

        previous_profile_number = next_profile_number - 1

        is_batch_boundary = (
            previous_profile_number > 0
            and previous_profile_number % (self._pacing_policy.requests_per_batch) == 0
        )

        if is_batch_boundary:
            print()
            print("[CRAWL REST]")

            print("A batch of Instagram profiles " "has been checked.")

            print("Cooling down before the next profile: " f"{delay:.0f} seconds.")

        else:
            print("  Waiting before next Instagram profile: " f"{delay:.0f}s")

        self._sleeper(delay)

    def fetch(
        self,
        username: str,
    ) -> RawProfileData:
        """Fetch one Instagram profile.

        Pacing happens once before this profile.

        If Instagram returns RateLimitError, only the
        RateLimitPolicy cooldown is used before retrying
        the exact same profile.
        """

        if self._is_stopped:
            raise CrawlSessionStoppedError(
                "Instagram crawl session " "has already been stopped."
            )

        # Support using session.fetch() without an explicit
        # `with session:` block as existing code/tests do.
        if not self._is_open:
            self.open()

        # Apply normal pacing ONCE for this distinct profile.
        self._wait_before_profile()

        self._profile_request_count += 1

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

                print()
                print("[RATE LIMIT]")

                print("Instagram requested a cooldown.")

                print(
                    f"Waiting {delay:.0f} seconds " "before retrying the same profile."
                )

                self._sleeper(delay)

                # Important:
                # no normal pacing here.
                #
                # This is a retry of the SAME profile,
                # not a new profile request.
                continue

            self._rate_limit_policy.register_success()

            return profile

    def close(
        self,
    ) -> None:
        """Close the underlying fetcher once."""

        if not self._is_open:
            return

        close_method = getattr(
            self._fetcher,
            "close",
            None,
        )

        if callable(close_method):
            close_method()

        self._is_open = False
