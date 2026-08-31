import pytest
from pydantic import ValidationError

from app.filters.profile_filter import (
    ProfileFilter,
    ProfileFilterEngine,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)


def make_profile(
    *,
    username: str,
    followers_count: int,
    is_shop: bool | None,
    category: ProfileCategory,
    shop_score: float | None,
) -> InstagramProfile:
    return InstagramProfile(
        username=username,
        profile_url=f"https://www.instagram.com/{username}/",
        followers_count=followers_count,
        is_shop=is_shop,
        category=category,
        shop_score=shop_score,
    )


def test_filters_by_is_shop() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="shop_profile",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="personal_profile",
            followers_count=5_000,
            is_shop=False,
            category=ProfileCategory.BEAUTY,
            shop_score=0.1,
        ),
    ]

    criteria = ProfileFilter(
        is_shop=True,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "shop_profile"


def test_filters_by_category() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="beauty_shop",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="home_shop",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.HOME,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        category=ProfileCategory.BEAUTY,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "beauty_shop"


def test_filters_by_min_followers() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="small_shop",
            followers_count=900,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="large_shop",
            followers_count=1_500,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        min_followers=1_000,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "large_shop"


def test_filters_by_max_followers() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="small_shop",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="large_shop",
            followers_count=20_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        max_followers=10_000,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "small_shop"


def test_filters_by_follower_range() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="too_small",
            followers_count=999,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="matched",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="too_large",
            followers_count=10_001,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        min_followers=1_000,
        max_followers=10_000,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "matched"


def test_follower_range_is_inclusive() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="min_boundary",
            followers_count=1_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="max_boundary",
            followers_count=10_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        min_followers=1_000,
        max_followers=10_000,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 2


def test_filters_by_min_shop_score() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="low_score",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.59,
        ),
        make_profile(
            username="high_score",
            followers_count=5_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
    ]

    criteria = ProfileFilter(
        min_shop_score=0.6,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "high_score"


def test_profile_without_shop_score_does_not_match_min_score() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="unclassified",
            followers_count=5_000,
            is_shop=None,
            category=ProfileCategory.BEAUTY,
            shop_score=None,
        ),
    ]

    criteria = ProfileFilter(
        min_shop_score=0.6,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert result == []


def test_combined_filters() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="perfect_match",
            followers_count=6_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.85,
        ),
        make_profile(
            username="wrong_category",
            followers_count=6_000,
            is_shop=True,
            category=ProfileCategory.HOME,
            shop_score=0.85,
        ),
        make_profile(
            username="too_many_followers",
            followers_count=15_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.85,
        ),
        make_profile(
            username="low_shop_score",
            followers_count=6_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.4,
        ),
        make_profile(
            username="not_shop",
            followers_count=6_000,
            is_shop=False,
            category=ProfileCategory.BEAUTY,
            shop_score=0.1,
        ),
    ]

    criteria = ProfileFilter(
        is_shop=True,
        category=ProfileCategory.BEAUTY,
        min_followers=1_000,
        max_followers=10_000,
        min_shop_score=0.6,
    )

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert len(result) == 1
    assert result[0].username == "perfect_match"


def test_empty_filter_matches_all_profiles() -> None:
    engine = ProfileFilterEngine()

    profiles = [
        make_profile(
            username="profile_1",
            followers_count=1_000,
            is_shop=True,
            category=ProfileCategory.BEAUTY,
            shop_score=0.8,
        ),
        make_profile(
            username="profile_2",
            followers_count=50_000,
            is_shop=False,
            category=ProfileCategory.HOME,
            shop_score=0.1,
        ),
    ]

    criteria = ProfileFilter()

    result = engine.filter(
        profiles=profiles,
        criteria=criteria,
    )

    assert result == profiles


def test_invalid_follower_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProfileFilter(
            min_followers=10_000,
            max_followers=1_000,
        )
