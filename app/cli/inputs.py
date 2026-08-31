from app.models.profile import ProfileCategory


def parse_compact_number(value: str) -> int:
    """Parses a compact string representation of a number (e.g., '10k', '1.5M', '50_000') into an integer.

    Supports suffix multipliers:
        - 'k' or 'K': 1,000
        - 'm' or 'M': 1,000,000
        - 'b' or 'B': 1,000,000,000

    Args:
        value: The string representation of a number.

    Returns:
        The evaluated whole integer value.

    Raises:
        ValueError: If the string is empty, improperly formatted, contains
            a negative value, or resolves to a fractional float.
    """
    # Clean and normalize input delimiters
    normalized = (
        value.strip().lower().replace(",", "").replace("_", "").replace(" ", "")
    )

    if not normalized:
        raise ValueError("Value cannot be empty.")

    multipliers: dict[str, int] = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
    }

    suffix = normalized[-1]

    # Handle suffix-based multiplier scaling (e.g., 1.5k -> 1500.0)
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
        # Standard numeric parsing without suffix
        try:
            result = float(normalized)

        except ValueError as exc:
            raise ValueError(f"Invalid number: {value}") from exc

    # Domain constraints validation
    if result < 0:
        raise ValueError("Value cannot be negative.")

    if not result.is_integer():
        raise ValueError("Final value must resolve " "to a whole number.")

    return int(result)


def read_optional_follower_count(prompt: str) -> int | None:
    """Prompts the user via CLI to input an optional follower count string.

    Loops continuously until a valid compact number is entered or the user
    submits an empty response.

    Args:
        prompt: The text message displayed to the user in CLI.

    Returns:
        An integer representing parsed follower count, or None if skipped.
    """
    while True:
        value = input(prompt).strip()

        # Skip filter on empty input
        if not value:
            return None

        try:
            return parse_compact_number(value)

        except ValueError:
            print("Invalid follower count.")

            print("Examples: " "10000, 10k, 1.5k, " "468k, 1m, 2.5m")


def read_optional_float(
    prompt: str,
    *,
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> float | None:
    """Prompts the user via CLI to enter an optional floating-point value within a range.

    Loops continuously until a valid float within [min_value, max_value] is entered
    or the input is left empty.

    Args:
        prompt: The text message displayed to the user in CLI.
        min_value: The lower bound threshold (inclusive). Defaults to 0.0.
        max_value: The upper bound threshold (inclusive). Defaults to 1.0.

    Returns:
        The validated float value, or None if skipped.
    """
    while True:
        value = input(prompt).strip()

        # Skip filter on empty input
        if not value:
            return None

        try:
            parsed = float(value)

        except ValueError:
            print("Please enter a valid number.")
            continue

        # Enforce range boundaries
        if parsed < min_value or parsed > max_value:
            print(f"Value must be between " f"{min_value} and " f"{max_value}.")
            continue

        return parsed


def read_optional_bool(prompt: str) -> bool | None:
    """Prompts the user via CLI to enter an optional boolean choice.

    Loops continuously until a recognized affirmation, negation, or wildcard/skip input is given.

    Args:
        prompt: The text message displayed to the user in CLI.

    Returns:
        True for affirmative inputs ('y', 'yes', 'true', '1'),
        False for negative inputs ('n', 'no', 'false', '0'),
        or None for skip inputs ('', 'all', 'any', '*').
    """
    while True:
        value = input(prompt).strip().lower()

        # Skip/wildcard inputs map to None
        if value in {
            "",
            "all",
            "any",
            "*",
        }:
            return None

        # Affirmative truths
        if value in {
            "y",
            "yes",
            "true",
            "1",
        }:
            return True

        # Negation truths
        if value in {
            "n",
            "no",
            "false",
            "0",
        }:
            return False

        print("Please enter y, n, all, " "or leave empty.")


def read_optional_category() -> ProfileCategory | None:
    """Displays an indexed selection menu of available ProfileCategory options in CLI.

    Loops continuously until a valid numeric index corresponding to a category is selected,
    or a wildcard/empty response is provided. Excludes `ProfileCategory.UNKNOWN`.

    Returns:
        The selected ProfileCategory enum instance, or None if skipped.
    """
    print()
    print("Available categories")
    print("--------------------")

    # Filter out UNKNOWN category from user selection
    categories = [
        category for category in ProfileCategory if category != ProfileCategory.UNKNOWN
    ]

    for index, category in enumerate(
        categories,
        start=1,
    ):
        print(f"{index}. " f"{category.value}")

    print()
    print("Leave empty or enter 'all' " "to include all categories.")

    while True:
        value = input("Category number: ").strip().lower()

        # Wildcard selection maps to None
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
            print("Please enter a valid " "category number or 'all'.")
            continue

        # Check bounds for 1-based index selection
        if index < 1 or index > len(categories):
            print("Category number is " "out of range.")
            continue

        return categories[index - 1]
