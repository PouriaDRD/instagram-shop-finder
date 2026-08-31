from app.cli.inputs import (
    read_optional_bool,
    read_optional_category,
    read_optional_float,
    read_optional_follower_count,
)
from app.config import PROFILES_FILE
from app.filters.profile_filter import (
    ProfileFilter,
    ProfileFilterEngine,
)
from app.models.profile import (
    InstagramProfile,
)
from app.storage.json_storage import (
    JsonProfileStorage,
)


def build_filter_from_input() -> ProfileFilter:
    print()
    print("Profile filters")
    print("===============")

    category = read_optional_category()

    print()
    print("Follower examples: " "10k, 1.5k, 468k, " "1m, 2.5m")

    min_followers = read_optional_follower_count(
        "Minimum followers " "(empty = no minimum): "
    )

    max_followers = read_optional_follower_count(
        "Maximum followers " "(empty = no maximum): "
    )

    while (
        min_followers is not None
        and max_followers is not None
        and min_followers > max_followers
    ):
        print()
        print("Minimum followers cannot " "be greater than maximum " "followers.")

        min_followers = read_optional_follower_count("Minimum followers: ")

        max_followers = read_optional_follower_count("Maximum followers: ")

    is_shop = read_optional_bool("Shop only? " "[y/n/empty = all]: ")

    min_shop_score = read_optional_float(
        "Minimum shop score " "(0.0 - 1.0, " "empty = none): "
    )

    return ProfileFilter(
        is_shop=is_shop,
        category=category,
        min_followers=min_followers,
        max_followers=max_followers,
        min_shop_score=min_shop_score,
    )


def run_filter_command() -> None:
    storage = JsonProfileStorage(PROFILES_FILE)

    filter_engine = ProfileFilterEngine()

    profiles = storage.get_all()

    if not profiles:
        print()
        print("No stored profiles found.")
        return

    criteria = build_filter_from_input()

    filtered_profiles = filter_engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    print_filter_results(
        profiles=profiles,
        filtered_profiles=(filtered_profiles),
    )


def print_filter_results(
    *,
    profiles: list[InstagramProfile],
    filtered_profiles: list[InstagramProfile],
) -> None:
    print()
    print("Filter result")
    print("=============")

    print(f"Stored profiles: " f"{len(profiles)}")

    print(f"Matched profiles: " f"{len(filtered_profiles)}")

    print()

    if not filtered_profiles:
        print("No profiles matched.")
        return

    for profile in filtered_profiles:
        print_filtered_profile(profile)


def print_filtered_profile(profile: InstagramProfile) -> None:
    shop_score = f"{profile.shop_score:.0%}" if profile.shop_score is not None else "-"

    print(f"@{profile.username}")

    print(f"  Followers: " f"{profile.followers_count:,}")

    print(f"  Category: " f"{profile.category.value}")

    print(f"  Is shop: " f"{profile.is_shop}")

    print(f"  Shop score: " f"{shop_score}")

    print()
