from app.classifiers.category_classifier import (
    CategoryClassifier,
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
) -> InstagramProfile:
    return InstagramProfile(
        username=username,
        profile_url=f"https://www.instagram.com/{username}/",
        display_name=display_name,
        bio=bio,
    )


def test_detects_beauty_category() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Beauty Shop",
        bio="فروش لوازم آرایشی، میکاپ و محصولات مراقبت پوست",
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.BEAUTY
    assert result.score > 0
    assert "آرایشی" in result.matched_signals
    assert "میکاپ" in result.matched_signals


def test_detects_clothing_category() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Women's Clothing",
        bio="فروش مانتو، شومیز، شلوار و لباس زنانه",
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.CLOTHING
    assert result.score > 0
    assert "مانتو" in result.matched_signals


def test_detects_home_category() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Home Decor",
        bio="دکوراسیون خانه و لوازم آشپزخانه",
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.HOME
    assert result.score > 0


def test_detects_accessories_category() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Accessory Store",
        bio="فروش گردنبند، دستبند، انگشتر و زیورآلات",
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.ACCESSORIES
    assert result.score > 0


def test_unknown_category_when_no_signal_exists() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Ali",
        bio="Travel, daily life and photography",
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.UNKNOWN
    assert result.score == 0.0
    assert result.matched_signals == ()


def test_empty_profile_is_unknown() -> None:
    classifier = CategoryClassifier()

    profile = make_profile()

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.UNKNOWN
    assert result.score == 0.0
    assert result.matched_signals == ()


def test_category_score_never_exceeds_one() -> None:
    classifier = CategoryClassifier()

    profile = make_profile(
        display_name="Beauty Makeup Skincare",
        bio=("آرایشی میکاپ پوست اسکین skincare makeup beauty " "رژ کرم ریمل"),
    )

    result = classifier.classify(profile)

    assert result.category == ProfileCategory.BEAUTY
    assert result.score == 1.0
