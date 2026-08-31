import pytest

from app.crawler.exceptions import (
    CrawlSessionStoppedError,
)
from app.crawler.rate_limit import (
    RateLimitPolicy,
)


def test_first_rate_limit_returns_30_seconds() -> None:
    policy = RateLimitPolicy()

    delay = policy.register_rate_limit()

    assert delay == 30.0

    assert policy.consecutive_rate_limits == 1


def test_second_rate_limit_returns_120_seconds() -> None:
    policy = RateLimitPolicy()

    policy.register_rate_limit()

    delay = policy.register_rate_limit()

    assert delay == 120.0

    assert policy.consecutive_rate_limits == 2


def test_third_rate_limit_stops_session() -> None:
    policy = RateLimitPolicy()

    policy.register_rate_limit()
    policy.register_rate_limit()

    with pytest.raises(CrawlSessionStoppedError):
        policy.register_rate_limit()


def test_retry_after_is_respected_when_longer() -> None:
    policy = RateLimitPolicy()

    delay = policy.register_rate_limit(retry_after_seconds=90.0)

    assert delay == 90.0


def test_policy_delay_wins_when_retry_after_is_shorter() -> None:
    policy = RateLimitPolicy()

    delay = policy.register_rate_limit(retry_after_seconds=5.0)

    assert delay == 30.0


def test_success_resets_rate_limit_counter() -> None:
    policy = RateLimitPolicy()

    policy.register_rate_limit()
    policy.register_rate_limit()

    policy.register_success()

    assert policy.consecutive_rate_limits == 0

    delay = policy.register_rate_limit()

    assert delay == 30.0


def test_custom_policy_is_supported() -> None:
    policy = RateLimitPolicy(
        cooldown_seconds=(
            10.0,
            20.0,
        ),
        max_consecutive_rate_limits=4,
    )

    assert policy.register_rate_limit() == 10.0

    assert policy.register_rate_limit() == 20.0

    assert policy.register_rate_limit() == 20.0


def test_zero_retry_after_is_ignored() -> None:
    policy = RateLimitPolicy()

    delay = policy.register_rate_limit(retry_after_seconds=0.0)

    assert delay == 30.0


def test_negative_retry_after_is_ignored() -> None:
    policy = RateLimitPolicy()

    delay = policy.register_rate_limit(retry_after_seconds=-10.0)

    assert delay == 30.0
