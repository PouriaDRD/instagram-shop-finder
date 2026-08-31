from app.classifiers.category_classifier import CategoryClassifier
from app.classifiers.shop_classifier import ShopClassifier, ShopVerdict
from app.config import PROFILES_FILE
from app.models.profile import InstagramProfile
from app.storage.json_storage import JsonProfileStorage


def apply_classifications(
    profile: InstagramProfile,
    *,
    shop_classifier: ShopClassifier,
    category_classifier: CategoryClassifier,
) -> InstagramProfile:
    updated_profile = profile.model_copy(deep=True)

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
    storage = JsonProfileStorage(PROFILES_FILE)

    profiles = storage.get_all()

    if not profiles:
        print()
        print("No stored profiles found.")
        return

    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    processed_count = 0

    print()
    print("Reprocessing saved profiles")
    print("===========================")

    for profile in profiles:
        updated_profile = apply_classifications(
            profile,
            shop_classifier=shop_classifier,
            category_classifier=(category_classifier),
        )

        storage.save(updated_profile)

        processed_count += 1

        shop_score = (
            f"{updated_profile.shop_score:.0%}"
            if updated_profile.shop_score is not None
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
        )

    print()
    print("Reprocess completed")
    print("-------------------")

    print(f"Processed profiles: " f"{processed_count}")
