import pytest

from app.cli.inputs import (
    parse_compact_number,
)


@pytest.mark.parametrize(
    (
        "raw",
        "expected",
    ),
    [
        (
            "10000",
            10_000,
        ),
        (
            "10,000",
            10_000,
        ),
        (
            "۱۰٬۰۰۰",
            10_000,
        ),
        (
            "۱۰،۰۰۰",
            10_000,
        ),
        (
            "10_000",
            10_000,
        ),
        (
            "10 000",
            10_000,
        ),
        (
            "10k",
            10_000,
        ),
        (
            "10K",
            10_000,
        ),
        (
            "10 k",
            10_000,
        ),
        (
            "۱۰k",
            10_000,
        ),
        (
            "10.5k",
            10_500,
        ),
        (
            "10.5K",
            10_500,
        ),
        (
            "500k",
            500_000,
        ),
        (
            "500 K",
            500_000,
        ),
        (
            "0.5m",
            500_000,
        ),
        (
            "0.5M",
            500_000,
        ),
        (
            "1m",
            1_000_000,
        ),
        (
            "1M",
            1_000_000,
        ),
        (
            "۱m",
            1_000_000,
        ),
        (
            "1.5m",
            1_500_000,
        ),
        (
            "۱٫۵m",
            1_500_000,
        ),
        (
            "10 هزار",
            10_000,
        ),
        (
            "۱۰ هزار",
            10_000,
        ),
        (
            "500 هزار",
            500_000,
        ),
        (
            "1 میلیون",
            1_000_000,
        ),
        (
            "۱ میلیون",
            1_000_000,
        ),
        (
            "1.5 میلیون",
            1_500_000,
        ),
        (
            "1 thousand",
            1_000,
        ),
        (
            "1 million",
            1_000_000,
        ),
        (
            "1b",
            1_000_000_000,
        ),
        (
            "1 billion",
            1_000_000_000,
        ),
        (
            "۱ میلیارد",
            1_000_000_000,
        ),
        (
            "10k+",
            10_000,
        ),
        (
            "500k+",
            500_000,
        ),
        (
            "10k followers",
            10_000,
        ),
        (
            "10K follower",
            10_000,
        ),
        (
            "۱۰ هزار فالوور",
            10_000,
        ),
    ],
)
def test_parse_compact_number_supported_formats(
    raw: str,
    expected: int,
) -> None:
    assert parse_compact_number(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "hello",
        "abc10k",
        "-10k",
        "k10",
        "10x",
        "ten thousand",
        "10kk",
    ],
)
def test_parse_compact_number_rejects_invalid_values(
    raw: str,
) -> None:
    with pytest.raises(ValueError):
        parse_compact_number(raw)
