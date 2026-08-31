from app.classifiers.shop_classifier import (
    ShopClassifier,
    ShopVerdict,
)
from app.models.profile import InstagramProfile


def make_profile(
    *,
    username: str = "test_profile",
    display_name: str | None = None,
    bio: str | None = None,
) -> InstagramProfile:
    return InstagramProfile(
        username=username,
        profile_url=(f"https://www.instagram.com/" f"{username}/"),
        display_name=display_name,
        bio=bio,
    )


def test_clear_shop_is_detected() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name="Beauty Store",
        bio=("فروش محصولات آرایشی، " "سفارش از دایرکت، " "ارسال سراسر کشور"),
    )

    result = classifier.classify(profile)

    assert result.verdict == ShopVerdict.SHOP

    assert result.score >= 0.6

    assert "فروش" in result.matched_signals

    assert "سفارش" in result.matched_signals

    assert "ارسال" in result.matched_signals

    assert "store" not in result.matched_signals


def test_sales_and_shipping_are_exactly_65_percent() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("فروش لوازم آرایشی " "و ارسال سراسر کشور"),
    )

    result = classifier.classify(profile)

    assert result.score == 0.65

    assert result.verdict == ShopVerdict.SHOP

    assert result.matched_signals == (
        "فروش",
        "ارسال",
    )


def test_display_name_shop_does_not_inflate_bio_score() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name=("Sample Beauty Shop"),
        bio=("فروش لوازم آرایشی " "و ارسال سراسر کشور"),
    )

    result = classifier.classify(profile)

    assert result.score == 0.65

    assert result.verdict == ShopVerdict.SHOP

    assert "shop" not in result.matched_signals


def test_store_in_display_name_is_supporting_evidence_only() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name="My Store",
    )

    result = classifier.classify(profile)

    assert result.score == 0.17

    assert result.verdict == ShopVerdict.UNKNOWN

    assert result.matched_signals == ("store",)


def test_persian_store_name_is_supporting_evidence_only() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name="فروشگاه آرایشی",
    )

    result = classifier.classify(profile)

    assert result.score == 0.23

    assert result.verdict == ShopVerdict.UNKNOWN

    assert result.matched_signals == ("فروشگاه",)


def test_products_plural_maps_to_product_signal() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("محصولات دست‌ساز " "اطلاعات در دایرکت"),
    )

    result = classifier.classify(profile)

    assert "محصول" in result.matched_signals

    assert "دایرکت" in result.matched_signals

    assert result.score == 0.16

    assert result.verdict == ShopVerdict.UNKNOWN


def test_shop_is_not_detected_inside_workshop() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("Photography workshop"),
    )

    result = classifier.classify(profile)

    assert "shop" not in result.matched_signals

    assert result.score == 0.0

    assert result.verdict == ShopVerdict.NOT_SHOP


def test_shop_is_not_detected_inside_shopper() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("Personal shopper " "and fashion lover"),
    )

    result = classifier.classify(profile)

    assert "shop" not in result.matched_signals


def test_store_is_not_detected_inside_storage() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("Cloud storage " "content creator"),
    )

    result = classifier.classify(profile)

    assert "store" not in result.matched_signals


def test_personal_profile_is_not_shop() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name="Sara",
        bio=("Lifestyle | travel | " "daily life"),
    )

    result = classifier.classify(profile)

    assert result.verdict == ShopVerdict.NOT_SHOP

    assert result.score == 0.0

    assert result.matched_signals == ()


def test_ambiguous_profile_is_unknown() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name=("Handmade Studio"),
        bio=("محصولات دست‌ساز " "اطلاعات بیشتر در دایرکت"),
    )

    result = classifier.classify(profile)

    assert result.verdict == ShopVerdict.UNKNOWN

    assert result.score == 0.16


def test_empty_bio_and_name_are_not_shop() -> None:
    classifier = ShopClassifier()

    profile = make_profile()

    result = classifier.classify(profile)

    assert result.verdict == ShopVerdict.NOT_SHOP

    assert result.score == 0.0

    assert result.matched_signals == ()


def test_strong_signal_has_more_weight_than_weak_signal() -> None:
    classifier = ShopClassifier()

    strong_profile = make_profile(
        bio="سفارش",
    )

    weak_profile = make_profile(
        bio="دایرکت",
    )

    strong_result = classifier.classify(strong_profile)

    weak_result = classifier.classify(weak_profile)

    assert strong_result.score > weak_result.score


def test_commercial_and_transaction_signals_get_bonus() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("سفارش محصول " "قیمت در دایرکت"),
    )

    result = classifier.classify(profile)

    assert result.score >= 0.6

    assert result.verdict == ShopVerdict.SHOP


def test_multiple_clear_signals_can_reach_full_score() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        display_name="Beauty Store",
        bio=("فروشگاه آرایشی | " "سفارش | ارسال | " "قیمت | موجودی"),
    )

    result = classifier.classify(profile)

    assert result.score == 1.0

    assert result.verdict == ShopVerdict.SHOP


def test_matching_is_case_insensitive() -> None:
    classifier = ShopClassifier()

    profile = make_profile(
        bio=("SHOP | ORDER | SHIPPING"),
    )

    result = classifier.classify(profile)

    assert result.verdict == ShopVerdict.SHOP

    assert "shop" in result.matched_signals

    assert "order" in result.matched_signals

    assert "shipping" in result.matched_signals
