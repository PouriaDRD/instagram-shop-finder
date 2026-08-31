from app.classifiers.category_classifier import (
    CategoryClassifier,
)
from app.classifiers.shop_classifier import (
    ShopClassifier,
)
from app.cli.reprocess_command import (
    apply_classifications,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)


def make_profile(
    *,
    username: str = "test_profile",
    display_name: str | None = None,
    bio: str | None = None,
    followers_count: int = 0,
    is_shop: bool | None = None,
    shop_score: float | None = None,
    category: ProfileCategory = (ProfileCategory.UNKNOWN),
) -> InstagramProfile:
    return InstagramProfile(
        username=username,
        profile_url=(f"https://www.instagram.com/" f"{username}/"),
        display_name=display_name,
        bio=bio,
        followers_count=followers_count,
        is_shop=is_shop,
        shop_score=shop_score,
        category=category,
    )


def test_reprocess_updates_shop_classification() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="clear_shop",
        display_name="Beauty Shop",
        bio=("فروشگاه لوازم آرایشی | " "سفارش | ارسال | قیمت"),
        is_shop=None,
        shop_score=None,
    )

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result.is_shop is True

    assert result.shop_score is not None

    assert result.shop_score >= 0.6

    assert len(result.shop_signals) > 0


def test_reprocess_updates_category() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="beauty_profile",
        display_name="Beauty Page",
        bio=("میکاپ، آرایشی، " "skincare"),
        category=(ProfileCategory.UNKNOWN),
    )

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result.category == ProfileCategory.BEAUTY


def test_reprocess_marks_personal_profile_as_not_shop() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="personal_profile",
        display_name="Sara",
        bio=("Travel | lifestyle | " "daily life"),
        is_shop=True,
        shop_score=0.9,
    )

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result.is_shop is False
    assert result.shop_score == 0.0

    assert result.shop_signals == ()


def test_reprocess_can_return_unknown_shop() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="ambiguous_profile",
        display_name="Handmade Studio",
        bio=("محصولات دست‌ساز " "اطلاعات در دایرکت"),
    )

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result.is_shop is None

    assert result.shop_score is not None

    assert result.shop_score == 0.16

    assert "محصول" in result.shop_signals

    assert "دایرکت" in result.shop_signals


def test_reprocess_does_not_mutate_original_profile() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="beauty_shop",
        display_name="Beauty Shop",
        bio=("فروشگاه آرایشی | " "سفارش | ارسال"),
        is_shop=None,
        shop_score=None,
        category=(ProfileCategory.UNKNOWN),
    )

    original = profile.model_copy(deep=True)

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result is not profile

    assert profile == original

    assert result.shop_score is not None

    assert result.category == ProfileCategory.BEAUTY


def test_reprocess_replaces_old_classification_values() -> None:
    shop_classifier = ShopClassifier()
    category_classifier = CategoryClassifier()

    profile = make_profile(
        username="changed_profile",
        display_name="Ali",
        bio=("Photography | travel"),
        is_shop=True,
        shop_score=1.0,
        category=(ProfileCategory.BEAUTY),
    )

    result = apply_classifications(
        profile,
        shop_classifier=shop_classifier,
        category_classifier=category_classifier,
    )

    assert result.is_shop is False
    assert result.shop_score == 0.0

    assert result.category == ProfileCategory.UNKNOWN
