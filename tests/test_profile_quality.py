from app.crawler.profile_quality import (
    ProfileQualityEvaluator,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)
from app.models.profile_quality import (
    ProfileDataQualityStatus,
)
from app.models.raw_profile import (
    RawProfileData,
)


def test_empty_profile_is_incomplete() -> None:
    raw = RawProfileData(
        username="example",
        display_name="",
        bio="",
        external_links=(),
        followers_count=0,
        following_count=0,
        posts_count=0,
        is_public=True,
    )

    profile = InstagramProfile(
        username="example",
        profile_url=("https://www.instagram.com/example/"),
        display_name="",
        bio="",
        external_links=(),
        followers_count=0,
        following_count=0,
        posts_count=0,
        is_public=True,
        category=(ProfileCategory.UNKNOWN),
        is_shop=False,
        shop_score=0.0,
        shop_signals=(),
    )

    result = ProfileQualityEvaluator().evaluate(
        raw=raw,
        profile=profile,
        expected_category=(ProfileCategory.BEAUTY),
        min_shop_score=0.25,
    )

    assert result.status == ProfileDataQualityStatus.INCOMPLETE


def test_normal_complete_shop_is_complete() -> None:
    raw = RawProfileData(
        username="shop",
        display_name=("فروشگاه آرایشی"),
        bio=("فروش محصولات آرایشی " "و ارسال به سراسر ایران"),
        external_links=(),
        followers_count=20_000,
        following_count=100,
        posts_count=200,
        is_public=True,
    )

    profile = InstagramProfile(
        username="shop",
        profile_url=("https://www.instagram.com/shop/"),
        display_name=("فروشگاه آرایشی"),
        bio=raw.bio,
        external_links=(),
        followers_count=20_000,
        following_count=100,
        posts_count=200,
        is_public=True,
        category=(ProfileCategory.BEAUTY),
        is_shop=True,
        shop_score=0.8,
        shop_signals=(
            "فروش",
            "ارسال",
            "فروشگاه",
        ),
    )

    result = ProfileQualityEvaluator().evaluate(
        raw=raw,
        profile=profile,
        expected_category=(ProfileCategory.BEAUTY),
        min_shop_score=0.25,
    )

    assert result.status == ProfileDataQualityStatus.COMPLETE


def test_all_zero_metrics_are_incomplete_even_with_text() -> None:
    raw = RawProfileData(
        username="example",
        display_name="Example Shop",
        bio="Some profile text",
        external_links=(),
        followers_count=0,
        following_count=0,
        posts_count=0,
        is_public=True,
    )

    profile = InstagramProfile(
        username="example",
        profile_url=("https://www.instagram.com/example/"),
        display_name="Example Shop",
        bio="Some profile text",
        external_links=(),
        followers_count=0,
        following_count=0,
        posts_count=0,
        is_public=True,
        category=(ProfileCategory.UNKNOWN),
        is_shop=False,
        shop_score=0.0,
        shop_signals=(),
    )

    result = ProfileQualityEvaluator().evaluate(
        raw=raw,
        profile=profile,
        expected_category=(ProfileCategory.CLOTHING),
        min_shop_score=0.30,
    )

    assert result.status == ProfileDataQualityStatus.INCOMPLETE
