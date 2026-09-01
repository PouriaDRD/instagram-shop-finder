import pytest

from app.crawler.pacing import (
    CrawlPacingPolicy,
)


def test_first_request_has_no_delay() -> None:
    policy = CrawlPacingPolicy()

    assert policy.delay_before_request(request_number=1) == 0


def test_normal_request_uses_base_delay() -> None:
    policy = CrawlPacingPolicy(
        delay_between_requests_seconds=8,
        requests_per_batch=8,
        batch_cooldown_seconds=45,
    )

    assert policy.delay_before_request(request_number=2) == 8


def test_first_request_after_batch_has_cooldown() -> None:
    policy = CrawlPacingPolicy(
        delay_between_requests_seconds=8,
        requests_per_batch=8,
        batch_cooldown_seconds=45,
    )

    assert policy.delay_before_request(request_number=9) == 53


def test_next_request_after_batch_returns_to_base_delay() -> None:
    policy = CrawlPacingPolicy(
        delay_between_requests_seconds=8,
        requests_per_batch=8,
        batch_cooldown_seconds=45,
    )

    assert policy.delay_before_request(request_number=10) == 8


@pytest.mark.parametrize(
    ("kwargs",),
    [
        (
            {
                "delay_between_requests_seconds": -1,
            },
        ),
        (
            {
                "requests_per_batch": 0,
            },
        ),
        (
            {
                "batch_cooldown_seconds": -1,
            },
        ),
    ],
)
def test_invalid_pacing_policy_rejected(
    kwargs,
) -> None:
    with pytest.raises(ValueError):
        CrawlPacingPolicy(**kwargs)
