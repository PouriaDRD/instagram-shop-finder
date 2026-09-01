from __future__ import annotations

import requests

from app.cli.inputs import (
    print_follower_count_help,
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
    DiscoveryResult,
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
from app.storage.profile_storage import (
    ProfileStorage,
)

INSTAGRAM_TEST_URL = "https://www.instagram.com/"

INSTAGRAM_TEST_TIMEOUT_SECONDS = 12


def _separator(
    *,
    char: str = "=",
    width: int = 64,
) -> None:
    print()
    print(char * width)


def _section(
    title: str,
    subtitle: str | None = None,
) -> None:
    _separator()

    print(title)

    if subtitle:
        print(subtitle)

    print(
        "="
        * min(
            len(title),
            64,
        )
    )

    print()


def _confirm(
    prompt: str,
    *,
    default_yes: bool = True,
) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"

    while True:
        answer = input(f"{prompt} {suffix}: ").strip().lower()

        if not answer:
            return default_yes

        if answer in {
            "y",
            "yes",
            "1",
        }:
            return True

        if answer in {
            "n",
            "no",
            "0",
        }:
            return False

        print("Please enter Y or N.")


def _confirm_vpn_off_for_discovery() -> bool:
    _section(
        "STEP 2 OF 3 - CANDIDATE DISCOVERY",
        "Public-web search",
    )

    print("For this step, VPN should be OFF.")

    print()

    print(
        "The program searches public directories "
        "and web results for Instagram usernames."
    )

    print("No Instagram profile will be opened yet.")

    print()

    print("[IMPORTANT] Every discovered username " "is saved immediately.")

    while True:
        print()

        answer = (
            input("Disconnect VPN and press ENTER " "to start (Q = cancel): ")
            .strip()
            .lower()
        )

        if not answer:
            print()
            print("[OK] VPN-OFF confirmation received.")

            return True

        if answer in {
            "q",
            "quit",
            "exit",
        }:
            print()
            print("[STOP] Discovery cancelled.")

            return False

        print("Press ENTER after disconnecting VPN, " "or Q to cancel.")


def _instagram_is_reachable() -> tuple[
    bool,
    str,
]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 "
            "Safari/537.36"
        ),
    }

    try:
        response = requests.get(
            INSTAGRAM_TEST_URL,
            headers=headers,
            timeout=(INSTAGRAM_TEST_TIMEOUT_SECONDS),
            allow_redirects=True,
        )

    except requests.RequestException as exc:
        return (
            False,
            str(exc),
        )

    if response.status_code >= 500:
        return (
            False,
            "HTTP " f"{response.status_code}",
        )

    return (
        True,
        "HTTP " f"{response.status_code}",
    )


def _wait_for_instagram_access(
    *,
    recovery: bool = False,
) -> bool:
    if recovery:
        _section(
            "INSTAGRAM CONNECTION PAUSED",
            "Network / VPN recovery",
        )

        print("Several Instagram requests failed.")

        print()

        print("Remaining candidates are safe.")

    else:
        _section(
            "STEP 3 OF 3 - INSTAGRAM CHECK",
            "Profile enrichment and filtering",
        )

        print("Candidate collection is complete.")

    print()

    print("For this step, VPN should be ON.")

    print()

    print("1. Connect your VPN.")

    print("2. Make sure Instagram opens normally.")

    print("3. Press ENTER.")

    while True:
        print()

        answer = input("VPN ready? Press ENTER " "(Q = stop safely): ").strip().lower()

        if answer in {
            "q",
            "quit",
            "exit",
        }:
            print()

            print("[STOP] Instagram crawling " "stopped safely.")

            return False

        if answer:
            print("Press ENTER when VPN is ready, " "or Q to stop.")

            continue

        print()

        print("Checking Instagram connectivity...")

        reachable, details = _instagram_is_reachable()

        if reachable:
            print("[OK] Instagram is reachable " f"({details}).")

            return True

        print("[FAILED] Instagram " "is not reachable.")

        print(f"Details: {details}")


def _show_configuration(
    criteria: DiscoveryCriteria,
) -> None:
    _section("SEARCH PLAN")

    category_label = (
        criteria.category.value if criteria.category is not None else "all categories"
    )

    print(f"Category           : " f"{category_label}")

    print(f"Target shops       : " f"{criteria.target_results}")

    min_label = (
        f"{criteria.min_followers:,}"
        if criteria.min_followers is not None
        else "no minimum"
    )

    max_label = (
        f"{criteria.max_followers:,}"
        if criteria.max_followers is not None
        else "no maximum"
    )

    print("Follower range     : " f"{min_label} to {max_label}")

    print("Minimum shop score : " f"{criteria.min_shop_score:.0%}")

    print("Search phrase      : " f"{criteria.additional_query or 'none'}")

    print()

    print("Candidate search budget:")

    print(
        f"  Up to " f"{criteria.max_candidates:,} " "unique usernames may be collected."
    )


def _show_final_summary(
    result: DiscoveryResult,
) -> None:
    _section("RUN SUMMARY")

    print("Candidates found        : " f"{result.discovered_candidates:,}")

    print("Instagram profiles read : " f"{result.checked_profiles:,}")

    print("Matched shops saved     : " f"{len(result.matched_profiles):,}")

    print("Rejected by filters     : " f"{result.rejected_profiles:,}")

    print("Incomplete / retry      : " f"{result.incomplete_profiles:,}")

    print("Clearly non-Iranian     : " f"{result.non_iranian_profiles:,}")

    print("Fetch failures          : " f"{result.failed_profiles:,}")

    print("Already saved           : " f"{result.skipped_existing:,}")

    if result.stopped_by_rate_limit:
        print()

        print(
            "[NOTICE] Instagram crawl "
            "stopped because the rate-limit "
            "safety threshold was reached."
        )


def run_discovery_command() -> None:
    _section(
        "INSTAGRAM SHOP FINDER",
        "Automatic shop discovery",
    )

    print("The process has 3 steps:")

    print()

    print("  1. Define search filters")

    print("  2. Discover candidate usernames")

    print("  3. Check candidates on Instagram")

    _section("STEP 1 OF 3 - SEARCH FILTERS")

    print("Choose the type of shop " "you want to find.")

    print()

    category = read_optional_category()

    print_follower_count_help()

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

        print("[ERROR] Minimum followers " "cannot be greater than maximum.")

        return

    print()

    print("Shop score is the main commercial " "qualification threshold.")

    print("Examples: 0.25 = permissive, " "0.60 = normal, 0.80 = strict.")

    print()

    min_shop_score = read_optional_float(
        "Minimum shop score " "(empty = 0.60): ",
        min_value=0.0,
        max_value=1.0,
    )

    if min_shop_score is None:
        min_shop_score = 0.60

    print()

    target_results = read_positive_int(
        "How many matching shops " "do you want? " "(empty = 20): ",
        default=20,
    )

    print()

    additional_query = input("Optional extra search phrase " "(empty = none): ").strip()

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
        min_shop_score=(min_shop_score),
        additional_query=(additional_query),
        max_candidates=(max_candidates),
    )

    _show_configuration(criteria)

    print()

    if not _confirm("Start with these settings?"):
        return

    storage = ProfileStorage(PROFILES_FILE)

    source = MultiSourceDiscoverySource(
        sources=(
            DirectoryDiscoverySource(
                max_pages_per_seed=2,
                request_delay_seconds=0.4,
            ),
            WebsiteInstagramLinkDiscoverySource(
                search_pages=3,
                max_sites_per_query=30,
            ),
            BingSearchDiscoverySource(
                max_pages_per_query=3,
            ),
            WebSearchDiscoverySource(
                max_pages_per_query=3,
            ),
        )
    )

    engine = InstagramShopDiscoveryEngine(
        source=source,
        storage=storage,
        before_crawl_callback=(lambda: (_wait_for_instagram_access(recovery=False))),
        network_recovery_callback=(lambda: (_wait_for_instagram_access(recovery=True))),
    )

    if not (_confirm_vpn_off_for_discovery()):
        return

    result = engine.discover(criteria)

    if result.matched_profiles:
        _section("MATCHED SHOPS")

        for index, profile in enumerate(
            result.matched_profiles,
            start=1,
        ):
            score = (
                f"{profile.shop_score:.0%}" if profile.shop_score is not None else "-"
            )

            print(f"{index:>2}. " f"@{profile.username}")

            print("    Followers : " f"{profile.followers_count:,}")

            print("    Category  : " f"{profile.category.value}")

            print("    Shop score: " f"{score}")

            print()

    _show_final_summary(result)

    print()

    print("Candidate state: " "data/candidates.json")

    print("Qualified shops: " "data/profiles.json")

    print()
