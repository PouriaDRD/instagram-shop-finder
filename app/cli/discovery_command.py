"""CLI command module for executing automatic Instagram shop discovery."""

from app.cli.inputs import (
    read_optional_category,
    read_optional_float,
    read_optional_follower_count,
    read_positive_int,
)
from app.config import PROFILES_FILE
from app.discovery.engine import (
    DiscoveryCriteria,
    InstagramShopDiscoveryEngine,
)
from app.discovery.web_search import (
    WebSearchDiscoverySource,
)
from app.storage.json_storage import (
    JsonProfileStorage,
)


def run_discovery_command() -> None:
    """Interactively prompts for discovery parameters and executes shop discovery.

    Guides the CLI user through category selection (allowing specific category targets or a global
    search across all categories), follower bounds, shop confidence thresholds, target result limits,
    and optional search phrases. Configures and delegates execution to `InstagramShopDiscoveryEngine`,
    printing matching profiles and a summary report upon completion.
    """
    print()
    print("Automatic Shop Discovery")
    print("========================")

    print()
    print("Choose a category or select all " "to search across every category.")

    # Optional category selection allows specifying a target or searching across all categories
    category = read_optional_category()

    print()

    # Gather optional numeric bounds for follower count filtering
    min_followers = read_optional_follower_count(
        "Minimum followers (empty = no minimum): "
    )

    max_followers = read_optional_follower_count(
        "Maximum followers (empty = no maximum): "
    )

    # Validate that range boundaries are logically consistent
    if (
        min_followers is not None
        and max_followers is not None
        and min_followers > max_followers
    ):
        print()
        print("Minimum followers cannot be " "greater than maximum followers.")
        return

    print()

    # Threshold score determines minimum confidence for shop classification
    min_shop_score = read_optional_float(
        "Minimum shop score (empty = 0.60): ",
        min_value=0.0,
        max_value=1.0,
    )

    if min_shop_score is None:
        min_shop_score = 0.60

    # Number of verified shop matches desired by the user
    target_results = read_positive_int(
        "How many matching shops do you want? (empty = 20): ",
        default=20,
    )

    print()

    # Optional query suffix for geographical or keyword filtering (e.g., city name)
    additional_query = input(
        "Additional search phrase (optional, e.g. تهران): "
    ).strip()

    if not additional_query:
        additional_query = None

    # Calculate dynamically scaled candidate limits capped between 50 and 500
    max_candidates = max(
        target_results * 10,
        50,
    )

    max_candidates = min(
        max_candidates,
        500,
    )

    # Assemble validated inputs into a DiscoveryCriteria specification instance
    criteria = DiscoveryCriteria(
        category=category,
        target_results=target_results,
        min_followers=min_followers,
        max_followers=max_followers,
        min_shop_score=min_shop_score,
        additional_query=additional_query,
        max_candidates=max_candidates,
    )

    # Initialize persistence layer and web search candidate source
    storage = JsonProfileStorage(PROFILES_FILE)
    source = WebSearchDiscoverySource()

    # Construct discovery engine coordinator
    engine = InstagramShopDiscoveryEngine(
        source=source,
        storage=storage,
    )

    print()
    print("Discovery started")
    print("-----------------")

    category_label = criteria.category.value if criteria.category is not None else "all"

    print(f"Category: {category_label}")
    print(f"Target matches: {criteria.target_results}")

    if criteria.min_followers is not None:
        print(f"Minimum followers: " f"{criteria.min_followers:,}")

    if criteria.max_followers is not None:
        print(f"Maximum followers: " f"{criteria.max_followers:,}")

    print(f"Minimum shop score: " f"{criteria.min_shop_score:.0%}")

    if criteria.additional_query:
        print(f"Additional phrase: " f"{criteria.additional_query}")

    print()

    # Execute discovery pipeline crawl and classification loop
    result = engine.discover(criteria)

    # Display itemized list of newly discovered matching shop profiles
    if result.matched_profiles:
        print("Matched shops")
        print("=============")

        for profile in result.matched_profiles:
            score = (
                f"{profile.shop_score:.0%}" if profile.shop_score is not None else "-"
            )

            print(
                f"@{profile.username}"
                f" | followers={profile.followers_count:,}"
                f" | category={profile.category.value}"
                f" | shop_score={score}"
            )

    else:
        print("No matching shops found " "in this discovery run.")

    # Render summary telemetry metrics for candidate filtering and pipeline diagnostics
    print()
    print("Discovery summary")
    print("=================")
    print("Candidates discovered: " f"{result.discovered_candidates}")
    print("Profiles checked: " f"{result.checked_profiles}")
    print("Matching shops saved: " f"{len(result.matched_profiles)}")
    print("Rejected by filters: " f"{result.rejected_profiles}")
    print("Fetch failures: " f"{result.failed_profiles}")
    print("Already stored/skipped: " f"{result.skipped_existing}")

    # Notify user if discovery was truncated to prevent Instagram rate-limit blocks
    if result.stopped_by_rate_limit:
        print()
        print(
            "Discovery stopped because the "
            "Instagram crawl session reached "
            "its rate-limit safety threshold."
        )
