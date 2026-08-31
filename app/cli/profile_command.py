from app.classifiers.category_classifier import (
    CategoryClassifier,
)
from app.classifiers.shop_classifier import (
    ShopClassifier,
    ShopVerdict,
)
from app.config import PROFILES_FILE
from app.crawler.crawl_session import (
    InstagramCrawlSession,
)
from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    ProfileFetchError,
)
from app.mappers.profile_mapper import (
    ProfileMapper,
)
from app.models.profile import (
    InstagramProfile,
)
from app.storage.json_storage import (
    JsonProfileStorage,
)


def run_profile_command() -> None:
    username = input("Instagram username: ").strip()

    if not username:
        print()
        print("Username cannot be empty.")
        return

    shop_classifier = ShopClassifier()

    category_classifier = CategoryClassifier()

    storage = JsonProfileStorage(PROFILES_FILE)

    try:
        with InstagramCrawlSession() as session:
            raw_profile = session.fetch(username)

    except CrawlSessionStoppedError as exc:
        print()
        print("Crawl session stopped")
        print("---------------------")
        print(exc)
        return

    except ProfileFetchError as exc:
        print()
        print("Profile fetch failed")
        print("--------------------")
        print(exc)
        return

    profile = ProfileMapper.from_raw(raw_profile)

    shop_classification = shop_classifier.classify(profile)

    profile.shop_score = shop_classification.score

    profile.shop_signals = shop_classification.matched_signals

    if shop_classification.verdict == ShopVerdict.SHOP:
        profile.is_shop = True

    elif shop_classification.verdict == ShopVerdict.NOT_SHOP:
        profile.is_shop = False

    else:
        profile.is_shop = None

    category_classification = category_classifier.classify(profile)

    profile.category = category_classification.category

    storage.save(profile)

    print_profile_details(
        profile=profile,
        shop_verdict=(shop_classification.verdict.value),
        shop_score=(shop_classification.score),
        shop_signals=(shop_classification.matched_signals),
        category_score=(category_classification.score),
        category_signals=(category_classification.matched_signals),
    )


def print_profile_details(
    *,
    profile: InstagramProfile,
    shop_verdict: str,
    shop_score: float,
    shop_signals: tuple[str, ...],
    category_score: float,
    category_signals: tuple[str, ...],
) -> None:
    print()
    print("Profile processed successfully")
    print("------------------------------")

    print(f"Username: " f"@{profile.username}")

    print(f"Name: " f"{profile.display_name}")

    print(f"Followers: " f"{profile.followers_count:,}")

    print(f"Following: " f"{profile.following_count:,}")

    print(f"Posts: " f"{profile.posts_count:,}")

    print(f"Public: " f"{profile.is_public}")

    print()
    print("Bio")
    print("---")

    print(profile.bio or "-")

    print()
    print("External links")
    print("--------------")

    if not profile.external_links:
        print("-")

    else:
        for link in profile.external_links:
            title = link.title or link.type.value

            print(f"{title}: " f"{link.url}")

    print()
    print("Shop classification")
    print("-------------------")

    print(f"Is shop: " f"{profile.is_shop}")

    print(f"Verdict: " f"{shop_verdict}")

    print(f"Score: " f"{shop_score:.0%}")

    print("Signals: " f"{', '.join(shop_signals) or '-'}")

    print()
    print("Category classification")
    print("-----------------------")

    print(f"Category: " f"{profile.category.value}")

    print(f"Score: " f"{category_score:.0%}")

    print("Signals: " f"{', '.join(category_signals) or '-'}")

    print()
    print("Saved to profiles.json")
