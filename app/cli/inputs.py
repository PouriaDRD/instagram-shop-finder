"""CLI input parsing and validation utilities for Instagram profile management."""

from app.models.profile import ProfileCategory


def parse_compact_number(value: str) -> int:
    """Parses compact string representations of numbers (e.g., '10k', '1.5m') into integers.

    Args:
        value: Raw input string containing digits and optional compact multipliers ('k', 'm', 'b').

    Returns:
        Extracted whole integer value.

    Raises:
        ValueError: If value is empty, missing a numeric prefix, invalid, negative,
            or resolves to a non-whole number.
    """
    normalized = (
        value.strip()
        .lower()
        .replace(
            ",",
            "",
        )
        .replace(
            "_",
            "",
        )
        .replace(
            " ",
            "",
        )
    )

    if not normalized:
        raise ValueError("Value cannot be empty.")

    multipliers: dict[
        str,
        int,
    ] = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
    }

    suffix = normalized[-1]

    # Evaluate compact suffix multiplier if present
    if suffix in multipliers:
        number_part = normalized[:-1]

        if not number_part:
            raise ValueError("Number is missing before suffix.")

        try:
            number = float(number_part)

        except ValueError as exc:
            raise ValueError(f"Invalid number: {value}") from exc

        result = number * multipliers[suffix]

    else:
        try:
            result = float(normalized)

        except ValueError as exc:
            raise ValueError(f"Invalid number: {value}") from exc

    if result < 0:
        raise ValueError("Value cannot be negative.")

    if not result.is_integer():
        raise ValueError("Final value must resolve to a whole number.")

    return int(result)


def read_positive_int(prompt: str, *, default: int | None = None) -> int:
    """Prompts CLI user for a positive whole integer with optional default fallback.

    Args:
        prompt: User display message.
        default: Fallback integer returned when input is empty.

    Returns:
        Validated positive integer.
    """
    while True:
        value = input(prompt).strip()

        if not value and default is not None:
            return default

        try:
            parsed = int(value)

        except ValueError:
            print("Please enter a positive whole number.")
            continue

        if parsed <= 0:
            print("Value must be greater than zero.")
            continue

        return parsed


def read_optional_follower_count(prompt: str) -> int | None:
    """Prompts CLI user for an optional follower count, allowing compact notation.

    Args:
        prompt: User display message.

    Returns:
        Parsed integer follower count, or None if skipped.
    """
    while True:
        value = input(prompt).strip()

        if not value:
            return None

        try:
            return parse_compact_number(value)

        except ValueError:
            print("Invalid follower count.")
            print("Examples: 10000, 10k, 1.5k, 468k, 1m, 2.5m")


def read_optional_float(
    prompt: str,
    *,
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> float | None:
    """Prompts CLI user for an optional float constrained within a specific numeric range.

    Args:
        prompt: User display message.
        min_value: Minimum allowable float bound.
        max_value: Maximum allowable float bound.

    Returns:
        Validated float value, or None if skipped.
    """
    while True:
        value = input(prompt).strip()

        if not value:
            return None

        try:
            parsed = float(value)

        except ValueError:
            print("Please enter a valid number.")
            continue

        if parsed < min_value or parsed > max_value:
            print(f"Value must be between {min_value} and {max_value}.")
            continue

        return parsed


def read_optional_bool(prompt: str) -> bool | None:
    """Prompts CLI user for an optional boolean input supporting common string representations.

    Args:
        prompt: User display message.

    Returns:
        True/False for affirmative/negative answers, or None for wildcards/empty inputs.
    """
    while True:
        value = input(prompt).strip().lower()

        # Wildcards or empty string resolve to None (filter bypassed)
        if value in {
            "",
            "all",
            "any",
            "*",
        }:
            return None

        if value in {
            "y",
            "yes",
            "true",
            "1",
        }:
            return True

        if value in {
            "n",
            "no",
            "false",
            "0",
        }:
            return False

        print("Please enter y, n, all, or leave empty.")


def read_optional_category() -> ProfileCategory | None:
    """Displays indexed list of available ProfileCategory options and prompts CLI user selection.

    Returns:
        Selected ProfileCategory enum member, or None if skipped/all selected.
    """
    print()
    print("Available categories")
    print("--------------------")

    # Filter out UNKNOWN category from user selection menu
    categories = [
        category for category in ProfileCategory if category != ProfileCategory.UNKNOWN
    ]

    for (
        index,
        category,
    ) in enumerate(
        categories,
        start=1,
    ):
        print(f"{index}. {category.value}")

    print()
    print("Leave empty or enter 'all' to include all categories.")

    while True:
        value = input("Category number: ").strip().lower()

        if value in {
            "",
            "all",
            "any",
            "*",
        }:
            return None

        try:
            index = int(value)

        except ValueError:
            print("Please enter a valid category number or 'all'.")
            continue

        if index < 1 or index > len(categories):
            print("Category number is out of range.")
            continue

        return categories[index - 1]
