import re
from app.models.profile import (
    ProfileCategory,
)

_PERSIAN_DIGITS = str.maketrans(
    {
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)


_SUFFIX_MULTIPLIERS: dict[
    str,
    int,
] = {
    "k": 1_000,
    "thousand": 1_000,
    "هزار": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "میلیون": 1_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
    "میلیارد": 1_000_000_000,
}


_FOLLOWER_WORDS = (
    "followers",
    "follower",
    "فالوورها",
    "فالوور",
)


def _normalize_numeric_text(
    value: str,
) -> str:
    text = value.strip()

    text = text.translate(_PERSIAN_DIGITS)

    # Persian decimal separator
    text = text.replace(
        "٫",
        ".",
    )

    # Thousands separators
    text = text.replace(
        "٬",
        "",
    )

    text = text.replace(
        "،",
        "",
    )

    text = text.replace(
        ",",
        "",
    )

    text = text.replace(
        "_",
        "",
    )

    text = text.strip()

    return text


def parse_compact_number(
    value: str,
) -> int:
    """
    Parse human-friendly follower counts.

    Supported examples:

        10000
        10,000
        ۱۰٬۰۰۰
        10k
        10.5k
        500K
        0.5m
        1M
        10 thousand
        10 هزار
        1 million
        ۱ میلیون
        1b
        1 billion
        10k+
        10k followers
        ۱۰ هزار فالوور
    """

    if not isinstance(
        value,
        str,
    ):
        raise ValueError("Follower count must be text.")

    text = _normalize_numeric_text(value)

    if not text:
        raise ValueError("Follower count cannot be empty.")

    text = text.casefold()

    # Remove optional trailing +
    text = re.sub(
        r"\+\s*$",
        "",
        text,
    ).strip()

    # Remove follower-related labels.
    for word in _FOLLOWER_WORDS:
        text = re.sub(
            rf"\b{re.escape(word)}\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    # Collapse repeated whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    # First try:
    # number + optional suffix
    match = re.fullmatch(
        (
            r"([0-9]+(?:\.[0-9]+)?)"
            r"\s*"
            r"(k|m|b|"
            r"thousand|million|billion|"
            r"هزار|میلیون|میلیارد)?"
        ),
        text,
        flags=re.IGNORECASE,
    )

    if match:
        number_text = match.group(1)

        suffix = match.group(2)

        try:
            number = float(number_text)

        except ValueError as exc:
            raise ValueError(f"Invalid follower count: {value}") from exc

        multiplier = 1

        if suffix:
            multiplier = _SUFFIX_MULTIPLIERS[suffix.casefold()]

        result = number * multiplier

        if result < 0:
            raise ValueError("Follower count cannot be negative.")

        if not result.is_integer():
            raise ValueError("Follower count must resolve " "to a whole number.")

        return int(result)

    # Support regular numbers containing spaces:
    #
    # 10 000
    #
    spaced_number = re.fullmatch(
        r"[0-9]+(?: [0-9]{3})+",
        text,
    )

    if spaced_number:
        return int(
            text.replace(
                " ",
                "",
            )
        )

    raise ValueError(
        (
            f"Invalid follower count: {value!r}. "
            "Examples: 10000, 10,000, 10k, "
            "10.5k, 500K, 0.5m, 10 هزار, "
            "۱ میلیون."
        )
    )


def print_follower_count_help() -> None:
    print()
    print("Follower count formats")
    print("----------------------")

    print("You can use any of these formats:")

    print()
    print("  Exact number : 10000")
    print("  Thousands    : 10,000")
    print("  Persian      : ۱۰٬۰۰۰")
    print("  Compact K    : 10k / 10K / 10.5k")
    print("  Compact M    : 0.5m / 1M")
    print("  Words        : 10 هزار / 1 میلیون")
    print("  Optional +   : 10k+ / 500k+")
    print("  Label        : 10k followers / " "۱۰ هزار فالوور")

    print()
    print("Examples: 10k = 10,000 | " "500k = 500,000 | " "1.5m = 1,500,000")


def read_optional_follower_count(
    prompt: str,
) -> int | None:
    while True:
        raw = input(prompt).strip()

        if not raw:
            return None

        try:
            return parse_compact_number(raw)

        except ValueError as exc:
            print()
            print(f"Invalid follower count: {exc}")

            print(
                "Examples: "
                "10000, 10,000, 10k, "
                "10.5k, 500k, 0.5m, "
                "10 هزار, ۱ میلیون"
            )

            print()


def read_positive_int(
    prompt: str,
    *,
    default: int | None = None,
) -> int:
    while True:
        raw = input(prompt).strip()

        if not raw:
            if default is not None:
                return default

            print("A value is required.")

            continue

        try:
            value = int(raw.translate(_PERSIAN_DIGITS))

        except ValueError:
            print("Please enter a valid integer.")

            continue

        if value <= 0:
            print("Value must be greater than zero.")

            continue

        return value


def read_optional_float(
    prompt: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float | None:
    while True:
        raw = input(prompt).strip()

        if not raw:
            return None

        normalized = (
            raw.translate(_PERSIAN_DIGITS)
            .replace(
                "٫",
                ".",
            )
            .replace(
                "،",
                ".",
            )
        )

        try:
            value = float(normalized)

        except ValueError:
            print("Please enter a valid number.")

            continue

        if min_value is not None and value < min_value:
            print(f"Value must be >= " f"{min_value}.")

            continue

        if max_value is not None and value > max_value:
            print(f"Value must be <= " f"{max_value}.")

            continue

        return value


def read_optional_bool(
    prompt: str,
) -> bool | None:
    while True:
        raw = input(prompt).strip().lower()

        if raw in {
            "",
            "all",
            "any",
            "*",
        }:
            return None

        if raw in {
            "y",
            "yes",
            "true",
            "1",
            "بله",
            "آره",
        }:
            return True

        if raw in {
            "n",
            "no",
            "false",
            "0",
            "خیر",
            "نه",
        }:
            return False

        print("Enter yes/no or leave empty.")


def read_optional_category(
    prompt: str = "Category: ",
) -> ProfileCategory | None:
    available_categories = [
        category
        for category in ProfileCategory
        if (category != ProfileCategory.UNKNOWN)
    ]

    print()
    print("Available categories:")

    for index, category in enumerate(
        available_categories,
        start=1,
    ):
        print(f"{index}. " f"{category.value}")

    print("0. all")

    while True:
        raw = input(prompt).strip()

        if raw.casefold() in {
            "",
            "0",
            "all",
            "any",
            "*",
        }:
            return None

        normalized = raw.casefold()

        for category in available_categories:
            if category.value.casefold() == normalized:
                return category

        try:
            index = int(raw.translate(_PERSIAN_DIGITS))

        except ValueError:
            index = -1

        if 1 <= index <= len(available_categories):
            return available_categories[index - 1]

        print("Invalid category. " "Choose a listed number/name " "or enter all.")
