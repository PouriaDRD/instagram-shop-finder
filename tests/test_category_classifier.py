from app.classifiers.category_classifier import (
    CategoryClassifier,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)


def make_profile(
    *,
    display_name: str | None = None,
    bio: str | None = None,
) -> InstagramProfile:
    return InstagramProfile(
        username="test_profile",
        profile_url=("https://www.instagram.com/" "test_profile/"),
        display_name=display_name,
        bio=bio,
    )


def test_beauty_category() -> None:
    result = CategoryClassifier().classify(make_profile(bio="میکاپ و makeup"))

    assert result.category == ProfileCategory.BEAUTY
    assert result.score == 0.25
    assert "میکاپ" in result.matched_signals


def test_clothing_category() -> None:
    result = CategoryClassifier().classify(make_profile(bio="فروش لباس و مانتو"))

    assert result.category == ProfileCategory.CLOTHING


def test_home_category() -> None:
    result = CategoryClassifier().classify(
        make_profile(bio=("لوازم خانگی و " "محصولات آشپزخانه"))
    )

    assert result.category == ProfileCategory.HOME


def test_accessories_category() -> None:
    result = CategoryClassifier().classify(make_profile(bio="گردنبند و دستبند"))

    assert result.category == ProfileCategory.ACCESSORIES


def test_unknown_category() -> None:
    result = CategoryClassifier().classify(make_profile(bio="Personal blog"))

    assert result.category == ProfileCategory.UNKNOWN
    assert result.score == 0.0


def test_display_name_is_used() -> None:
    result = CategoryClassifier().classify(
        make_profile(display_name=("فروشگاه لباس زیر"))
    )

    assert result.category == ProfileCategory.CLOTHING


def test_more_matches_have_higher_score() -> None:
    classifier = CategoryClassifier()

    one = classifier.classify(make_profile(bio="لباس"))

    two = classifier.classify(make_profile(bio="لباس مانتو"))

    assert two.score > one.score


def test_saat_in_saaate_does_not_mean_accessories() -> None:
    result = CategoryClassifier().classify(
        make_profile(bio=("پشتیبانی ۲۴ ساعته تلفنی " "و تلگرامی"))
    )

    assert result.category != ProfileCategory.ACCESSORIES

    assert "ساعت" not in result.matched_signals


def test_baneh_bosch_is_home() -> None:
    result = CategoryClassifier().classify(
        make_profile(
            display_name=("فروشگاه لوازم خانگی | " "بانه بوش"),
            bio=("ارسال به سراسر کشور " "و تضمین اصالت کالا"),
        )
    )

    assert result.category == ProfileCategory.HOME


def test_imajazi_shop_is_not_accessories() -> None:
    result = CategoryClassifier().classify(
        make_profile(
            display_name=("مجازی شاپ | " "خرید مطمئن استارز تلگرام"),
            bio=("پشتیبانی ۲۴ ساعته تلفنی " "و تلگرامی"),
        )
    )

    assert result.category == ProfileCategory.UNKNOWN


def test_shortologist_is_clothing() -> None:
    result = CategoryClassifier().classify(
        make_profile(
            display_name=("شورتولوژیست|شورت|جوراب"),
        )
    )

    assert result.category == ProfileCategory.CLOTHING

    assert "شورت" in result.matched_signals


def test_jjpoosh_underwear_is_clothing() -> None:
    result = CategoryClassifier().classify(
        make_profile(
            display_name=("شورتولوژیست|شورت|جوراب"),
            bio=("ثبت سفارشسايت و " "دايركتوحضوري"),
        )
    )

    assert result.category == ProfileCategory.CLOTHING
