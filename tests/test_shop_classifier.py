from pydantic import HttpUrl
from app.classifiers.shop_classifier import (
    ShopClassifier,
    ShopVerdict,
)
from app.models.external_link import (
    ExternalLink,
    ExternalLinkType,
)
from app.models.profile import (
    InstagramProfile,
)


def make_profile(
    *,
    username: str = "test_profile",
    display_name: str | None = None,
    bio: str | None = None,
    external_links: tuple[ExternalLink, ...] = (),
) -> InstagramProfile:
    return InstagramProfile(
        username=username,
        profile_url=(f"https://www.instagram.com/" f"{username}/"),
        display_name=display_name,
        bio=bio,
        external_links=external_links,
    )


def website(
    url: str,
) -> ExternalLink:
    return ExternalLink(
        url=HttpUrl(url),
        type=ExternalLinkType.WEBSITE,
    )


def link_in_bio(
    url: str,
) -> ExternalLink:
    return ExternalLink(
        url=HttpUrl(url),
        type=ExternalLinkType.LINK_IN_BIO,
    )


def test_clear_shop_is_detected() -> None:
    result = ShopClassifier().classify(
        make_profile(bio=("فروش محصولات آرایشی " "سفارش از دایرکت " "ارسال سراسر کشور"))
    )

    assert result.verdict == ShopVerdict.SHOP


def test_sales_and_shipping_are_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(bio=("فروش لوازم آرایشی " "و ارسال سراسر کشور"))
    )

    assert result.score == 0.65
    assert result.verdict == ShopVerdict.SHOP


def test_shop_inside_workshop_is_not_detected() -> None:
    result = ShopClassifier().classify(make_profile(bio="Photography workshop"))

    assert "shop" not in result.matched_signals


def test_shop_inside_shopper_is_not_detected() -> None:
    result = ShopClassifier().classify(make_profile(bio="Personal shopper"))

    assert "shop" not in result.matched_signals


def test_products_plural_is_detected() -> None:
    result = ShopClassifier().classify(
        make_profile(bio=("محصولات دست ساز " "اطلاعات در دایرکت"))
    )

    assert "محصول" in result.matched_signals
    assert result.score == 0.16


def test_personal_page_is_not_shop() -> None:
    result = ShopClassifier().classify(make_profile(bio="Travel lifestyle"))

    assert result.verdict == ShopVerdict.NOT_SHOP


def test_empty_profile_is_not_shop() -> None:
    result = ShopClassifier().classify(make_profile())

    assert result.score == 0.0


def test_link_alone_does_not_make_creator_a_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(
            bio=("content creator makeup"),
            external_links=(link_in_bio("https://takl.ink/test"),),
        )
    )

    assert result.score == 0.0
    assert result.verdict == ShopVerdict.NOT_SHOP


def test_lebaszirnikoo_is_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(
            username="lebaszirnikoo",
            display_name=("فروشگاه لباس زیر|لباس خواب"),
            bio=("ثبت از دایرکت و بزودی سایت " "پشتیبانی ۱۱ الی ۲۱"),
            external_links=(website("https://www.lebaszirnikoo.ir/"),),
        )
    )

    assert result.verdict == ShopVerdict.SHOP

    assert result.score >= 0.6


def test_baneh_bosch_is_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(
            display_name=("فروشگاه لوازم خانگی | بانه بوش"),
            bio=("تضمین اصالت کالا " "ارسال به سراسر کشور"),
            external_links=(link_in_bio("https://zil.ink/baneh.bosch"),),
        )
    )

    assert result.verdict == ShopVerdict.SHOP


def test_ali_karimi_is_not_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(
            display_name="Ali Karimi",
            bio="HumanRights ايران اگاهی آزادی",
        )
    )

    assert result.verdict == ShopVerdict.NOT_SHOP


def test_imajazishop_is_shop() -> None:
    result = ShopClassifier().classify(
        make_profile(
            display_name=("مجازی شاپ | " "خرید مطمئن استارز تلگرام"),
            bio=("استارز تلگرام و تلگرام پریمیوم " "با پشتیبانی ۲۴ ساعته"),
            external_links=(website("https://majazi.shop/"),),
        )
    )

    assert result.verdict == ShopVerdict.SHOP

    assert "شاپ" in result.matched_signals


def test_commercial_external_site_increases_score() -> None:
    classifier = ShopClassifier()

    without_site = classifier.classify(
        make_profile(
            display_name="مجازی شاپ",
        )
    )

    with_site = classifier.classify(
        make_profile(
            display_name="مجازی شاپ",
            external_links=(website("https://example.com"),),
        )
    )

    assert with_site.score > without_site.score


def test_strong_commercial_profile_can_reach_full_score() -> None:
    result = ShopClassifier().classify(
        make_profile(
            display_name="Beauty Shop",
            bio=("فروشگاه آرایشی سفارش " "ارسال قیمت موجودی"),
            external_links=(website("https://example.com"),),
        )
    )

    assert result.score == 1.0


def test_matching_is_case_insensitive() -> None:
    result = ShopClassifier().classify(make_profile(bio="SHOP ORDER SHIPPING"))

    assert result.verdict == ShopVerdict.SHOP
