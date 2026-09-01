from app.classifiers.category_classifier import CategoryClassifier
from app.classifiers.link_classifier import LinkClassifier
from app.classifiers.shop_classifier import ShopClassifier, ShopVerdict
from app.config import PROFILES_FILE
from app.models.external_link import ExternalLink
from app.models.profile import InstagramProfile
from app.storage.profile_storage import ProfileStorage


def apply_classifications(
    profile: InstagramProfile,
    *,
    shop_classifier: ShopClassifier,
    category_classifier: CategoryClassifier,
    link_classifier: LinkClassifier | None = None,
) -> InstagramProfile:
    updated_profile = profile.model_copy(deep=True)

    effective_link_classifier = (
        link_classifier if link_classifier is not None else LinkClassifier()
    )

    updated_links: list[ExternalLink] = []

    for link in updated_profile.external_links:
        detected_type = effective_link_classifier.classify(
            url=str(link.url),
            title=link.title,
        )

        updated_links.append(
            ExternalLink(
                url=link.url,
                title=link.title,
                type=detected_type,
            )
        )

    updated_profile.external_links = tuple(updated_links)

    shop_classification = shop_classifier.classify(updated_profile)

    updated_profile.shop_score = shop_classification.score

    updated_profile.shop_signals = shop_classification.matched_signals

    if shop_classification.verdict == ShopVerdict.SHOP:
        updated_profile.is_shop = True

    elif shop_classification.verdict == ShopVerdict.NOT_SHOP:
        updated_profile.is_shop = False

    else:
        updated_profile.is_shop = None

    category_classification = category_classifier.classify(updated_profile)

    updated_profile.category = category_classification.category

    return updated_profile


def run_reprocess_command() -> None:
    storage = ProfileStorage(PROFILES_FILE)

    profiles = storage.get_all()

    if not profiles:
        print()
        print("No stored profiles found.")
        return

    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()
    link_classifier = LinkClassifier()

    processed_count = 0

    print()
    print("Reprocessing saved profiles")
    print("===========================")

    for profile in profiles:
        updated_profile = apply_classifications(
            profile,
            shop_classifier=shop_classifier,
            category_classifier=(category_classifier),
            link_classifier=(link_classifier),
        )

        storage.save(updated_profile)

        processed_count += 1

        shop_score = (
            f"{updated_profile.shop_score:.0%}"
            if updated_profile.shop_score is not None
            else "-"
        )

        link_types = (
            ", ".join(link.type.value for link in updated_profile.external_links)
            if updated_profile.external_links
            else "-"
        )

        print(
            f"@{updated_profile.username}"
            f" | category="
            f"{updated_profile.category.value}"
            f" | is_shop="
            f"{updated_profile.is_shop}"
            f" | shop_score="
            f"{shop_score}"
            f" | links="
            f"{link_types}"
        )

    print()
    print("Reprocess completed")
    print("-------------------")
    print(f"Processed profiles: " f"{processed_count}")
