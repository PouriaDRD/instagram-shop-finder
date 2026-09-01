from collections.abc import Callable

import pytest

from app.crawler.crawl_session import (
    InstagramCrawlSession,
)
from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    RateLimitError,
)
from app.crawler.rate_limit import (
    RateLimitPolicy,
)
from app.models.raw_profile import (
    RawProfileData,
)


class FakeFetcher:
    def __init__(
        self,
        actions: list[RawProfileData | Exception],
    ) -> None:
        self._actions = list(actions)

        self.open_calls = 0
        self.close_calls = 0
        self.fetch_calls = 0

    def open(
        self,
    ) -> None:
        self.open_calls += 1

    def close(
        self,
    ) -> None:
        self.close_calls += 1

    def fetch(
        self,
        username: str,
    ) -> RawProfileData:
        self.fetch_calls += 1

        if not self._actions:
            raise AssertionError("No fake action configured.")

        action = self._actions.pop(0)

        if isinstance(
            action,
            Exception,
        ):
            raise action

        return action


def make_profile(
    username: str = "testshop",
) -> RawProfileData:
    return RawProfileData(
        username=username,
        display_name="Test Shop",
        followers_count=1000,
    )


def make_session(
    *,
    fetcher: FakeFetcher,
    sleeper: Callable[
        [float],
        None,
    ],
) -> InstagramCrawlSession:
    return InstagramCrawlSession(
        fetcher=fetcher,  # type: ignore[arg-type]
        sleeper=sleeper,
    )


def test_session_opens_and_closes_fetcher() -> None:
    fetcher = FakeFetcher(
        [
            make_profile(),
        ]
    )

    session = make_session(
        fetcher=fetcher,
        sleeper=lambda _: None,
    )

    with session:
        result = session.fetch("testshop")

        assert result.username == "testshop"

    assert fetcher.open_calls == 1
    assert fetcher.close_calls == 1


def test_successful_fetch_does_not_sleep() -> None:
    fetcher = FakeFetcher(
        [
            make_profile(),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    result = session.fetch("testshop")

    assert result.username == "testshop"
    assert sleeps == []


def test_first_429_waits_then_retries() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            make_profile(),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    result = session.fetch("testshop")

    assert result.username == "testshop"

    assert sleeps == [
        30.0,
    ]

    assert fetcher.fetch_calls == 2


def test_retry_after_is_used() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError(
                "429",
                retry_after_seconds=90.0,
            ),
            make_profile(),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    session.fetch("testshop")

    assert sleeps == [
        90.0,
    ]


def test_two_rate_limits_use_progressive_backoff() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            RateLimitError("429"),
            make_profile(),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    result = session.fetch("testshop")

    assert result.username == "testshop"

    assert sleeps == [
        30.0,
        120.0,
    ]

    assert fetcher.fetch_calls == 3


def test_third_rate_limit_stops_session() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            RateLimitError("429"),
            RateLimitError("429"),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    with pytest.raises(CrawlSessionStoppedError):
        session.fetch("testshop")

    assert session.is_stopped is True

    assert sleeps == [
        30.0,
        120.0,
    ]


def test_stopped_session_cannot_fetch_again() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            RateLimitError("429"),
            RateLimitError("429"),
        ]
    )

    session = make_session(
        fetcher=fetcher,
        sleeper=lambda _: None,
    )

    with pytest.raises(CrawlSessionStoppedError):
        session.fetch("first")

    with pytest.raises(CrawlSessionStoppedError):
        session.fetch("second")


def test_success_resets_rate_limit_counter() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            make_profile("first"),
            RateLimitError("429"),
            make_profile("second"),
        ]
    )

    sleeps: list[float] = []

    session = make_session(
        fetcher=fetcher,
        sleeper=sleeps.append,
    )

    first = session.fetch("first")

    second = session.fetch("second")

    assert first.username == "first"

    assert second.username == "second"

    expected_pacing_delay = session._pacing_policy.delay_before_request(
        request_number=2
    )

    assert sleeps == [
        30.0,
        expected_pacing_delay,
        30.0,
    ]


def test_custom_policy_can_be_injected() -> None:
    fetcher = FakeFetcher(
        [
            RateLimitError("429"),
            make_profile(),
        ]
    )

    sleeps: list[float] = []

    policy = RateLimitPolicy(
        cooldown_seconds=(5.0,),
        max_consecutive_rate_limits=2,
    )

    session = InstagramCrawlSession(
        fetcher=fetcher,  # type: ignore[arg-type]
        rate_limit_policy=policy,
        sleeper=sleeps.append,
    )

    session.fetch("testshop")

    assert sleeps == [
        5.0,
    ]
