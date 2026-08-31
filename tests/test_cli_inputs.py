import pytest

from app.cli.inputs import parse_compact_number


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1000", 1_000),
        ("10k", 10_000),
        ("10K", 10_000),
        ("1.5k", 1_500),
        ("468k", 468_000),
        ("1m", 1_000_000),
        ("2.5m", 2_500_000),
        ("1M", 1_000_000),
        ("1b", 1_000_000_000),
        ("2.5b", 2_500_000_000),
        ("10,000", 10_000),
        ("1,000,000", 1_000_000),
        ("10_000", 10_000),
        (" 10k ", 10_000),
    ],
)
def test_parse_compact_number(
    raw_value: str,
    expected: int,
) -> None:
    result = parse_compact_number(raw_value)

    assert result == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        " ",
        "abc",
        "ten",
        "k",
        "m",
        "1kk",
        "10x",
        "-10",
        "-5k",
    ],
)
def test_parse_compact_number_rejects_invalid_values(
    raw_value: str,
) -> None:
    with pytest.raises(ValueError):
        parse_compact_number(raw_value)


def test_parse_compact_number_accepts_decimal_suffix() -> None:
    result = parse_compact_number("12.5k")

    assert result == 12_500


def test_parse_compact_number_accepts_plain_decimal_if_integer_result() -> None:
    result = parse_compact_number("1000.0")

    assert result == 1_000


def test_parse_compact_number_rejects_fractional_final_value() -> None:
    with pytest.raises(ValueError):
        parse_compact_number("1.2345k")
