from app.cli.inputs import (
    read_optional_category,
    read_optional_float,
    read_optional_follower_count,
    read_positive_int,
)
from app.config import (
    PROFILES_FILE,
)
from app.discovery.bing_search import (
    BingSearchDiscoverySource,
)
from app.discovery.directory_source import (
    DirectoryDiscoverySource,
)
from app.discovery.engine import (
    DiscoveryCriteria,
    InstagramShopDiscoveryEngine,
)
from app.discovery.multi_source import (
    MultiSourceDiscoverySource,
)
from app.discovery.web_search import (
    WebSearchDiscoverySource,
)
from app.discovery.website_instagram import (
    WebsiteInstagramLinkDiscoverySource,
)
from app.storage.json_storage import (
    JsonProfileStorage,
)


def run_discovery_command() -> None:
    print()
    print("Automatic Shop Discovery")
    print("========================")

    print()
    print("Choose a category or select all " "to search across every category.")

    category = read_optional_category()

    print()

    min_followers = read_optional_follower_count(
        "Minimum followers " "(empty = no minimum): "
    )

    max_followers = read_optional_follower_count(
        "Maximum followers " "(empty = no maximum): "
    )

    if (
        min_followers is not None
        and max_followers is not None
        and min_followers > max_followers
    ):
        print()
        print("Minimum followers cannot be " "greater than maximum followers.")
        return

    print()

    min_shop_score = read_optional_float(
        ("Minimum shop score " "(empty = 0.60): "),
        min_value=0.0,
        max_value=1.0,
    )

    if min_shop_score is None:
        min_shop_score = 0.60

    target_results = read_positive_int(
        ("How many matching shops " "do you want? " "(empty = 20): "),
        default=20,
    )

    print()

    additional_query = input(
        ("Additional search phrase " "(optional, e.g. تهران): ")
    ).strip()

    if not additional_query:
        additional_query = None

    max_candidates = max(
        target_results * 25,
        150,
    )

    max_candidates = min(
        max_candidates,
        1500,
    )

    criteria = DiscoveryCriteria(
        category=category,
        target_results=target_results,
        min_followers=min_followers,
        max_followers=max_followers,
        min_shop_score=min_shop_score,
        additional_query=additional_query,
        max_candidates=max_candidates,
    )

    storage = JsonProfileStorage(PROFILES_FILE)

    source = MultiSourceDiscoverySource(
        sources=(
            # High-precision curated public shop lists.
            DirectoryDiscoverySource(
                max_pages_per_seed=2,
                request_delay_seconds=0.4,
            ),
            # Search public web for shop websites,
            # then extract their Instagram links.
            WebsiteInstagramLinkDiscoverySource(
                search_pages=3,
                max_sites_per_query=30,
            ),
            # Direct Bing Instagram result discovery.
            BingSearchDiscoverySource(
                max_pages_per_query=3,
            ),
            # DuckDuckGo/public HTML fallback.
            WebSearchDiscoverySource(
                max_pages_per_query=3,
            ),
        )
    )

    engine = InstagramShopDiscoveryEngine(
        source=source,
        storage=storage,
    )

    print()
    print("Discovery started")
    print("-----------------")

    category_label = criteria.category.value if criteria.category is not None else "all"

    print(f"Category: {category_label}")

    print(f"Target matches: " f"{criteria.target_results}")

    if criteria.min_followers is not None:
        print("Minimum followers: " f"{criteria.min_followers:,}")

    if criteria.max_followers is not None:
        print("Maximum followers: " f"{criteria.max_followers:,}")

    print("Minimum shop score: " f"{criteria.min_shop_score:.0%}")

    if criteria.additional_query:
        print("Additional phrase: " f"{criteria.additional_query}")

    print("Candidate sources: " "directories + shop websites " "+ Bing + DuckDuckGo")

    print()

    result = engine.discover(criteria)

    if result.matched_profiles:
        print()
        print("Matched shops")
        print("=============")

        for profile in result.matched_profiles:
            score = (
                f"{profile.shop_score:.0%}" if profile.shop_score is not None else "-"
            )

            print(
                f"@{profile.username}"
                f" | followers="
                f"{profile.followers_count:,}"
                f" | category="
                f"{profile.category.value}"
                f" | shop_score="
                f"{score}"
            )

    else:
        print("No matching shops found " "in this discovery run.")

    print()
    print("Discovery summary")
    print("=================")

    print("Candidates discovered: " f"{result.discovered_candidates}")

    print("Profiles checked: " f"{result.checked_profiles}")

    print("Matching shops saved: " f"{len(result.matched_profiles)}")

    print("Rejected by filters: " f"{result.rejected_profiles}")

    print("Fetch failures: " f"{result.failed_profiles}")

    print("Already stored/skipped: " f"{result.skipped_existing}")

    if result.stopped_by_rate_limit:
        print()
        print(
            "Discovery stopped because the "
            "Instagram crawl session reached "
            "its rate-limit safety threshold."
        )
