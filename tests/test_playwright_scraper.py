from pydantic import HttpUrl

from app.crawler.playwright_scraper import (
    InstagramPlaywrightProfileFetcher,
)
from app.models.external_link import (
    ExternalLink,
    ExternalLinkType,
)


def make_fetcher() -> InstagramPlaywrightProfileFetcher:
    return InstagramPlaywrightProfileFetcher()


def test_parse_compact_count_k() -> None:
    assert InstagramPlaywrightProfileFetcher._parse_compact_count("468K") == 468_000


def test_parse_compact_count_m() -> None:
    assert InstagramPlaywrightProfileFetcher._parse_compact_count("1.5M") == 1_500_000


def test_parse_compact_count_decimal_m() -> None:
    assert InstagramPlaywrightProfileFetcher._parse_compact_count("13.5M") == 13_500_000


def test_parse_plain_count() -> None:
    assert InstagramPlaywrightProfileFetcher._parse_compact_count("331") == 331


def test_extract_stats() -> None:
    fetcher = make_fetcher()

    text = "331 posts, " "468K followers, " "222 following"

    assert (
        fetcher._extract_count(
            text=text,
            label="followers",
        )
        == 468_000
    )

    assert (
        fetcher._extract_count(
            text=text,
            label="following",
        )
        == 222
    )

    assert (
        fetcher._extract_count(
            text=text,
            label="posts",
        )
        == 331
    )


def test_extract_count_returns_none_when_missing() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._extract_count(
            text="no statistics here",
            label="followers",
        )
        is None
    )


def test_metric_prefers_visible_header_over_meta() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_count_with_fallback(
        label="followers",
        header_text=("13.5M followers"),
        description=("14M followers, " "375 following, " "846 posts"),
        body_text=("15M followers"),
    )

    assert result == 13_500_000


def test_metric_falls_back_to_meta_when_header_missing() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_count_with_fallback(
        label="followers",
        header_text=("341 following\n" "846 posts"),
        description=("14M followers, " "375 following, " "846 posts"),
        body_text=("15M followers"),
    )

    assert result == 14_000_000


def test_each_metric_uses_fallback_independently() -> None:
    fetcher = make_fetcher()

    header_text = "13.5M followers\n" "341 following"

    description = "14M followers, " "375 following, " "846 posts"

    followers = fetcher._extract_count_with_fallback(
        label="followers",
        header_text=header_text,
        description=description,
        body_text="",
    )

    following = fetcher._extract_count_with_fallback(
        label="following",
        header_text=header_text,
        description=description,
        body_text="",
    )

    posts = fetcher._extract_count_with_fallback(
        label="posts",
        header_text=header_text,
        description=description,
        body_text="",
    )

    assert followers == 13_500_000
    assert following == 341
    assert posts == 846


def test_clean_unicode_text() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._clean_unicode_text("\u200eستایش مسجدی\u200f")
        == "ستایش مسجدی"
    )


def test_display_name() -> None:
    result = InstagramPlaywrightProfileFetcher._parse_display_name(
        ("ستایش مسجدی " "(@setayeshmasjedii) " "• Instagram")
    )

    assert result == "ستایش مسجدی"


def test_meta_boilerplate_is_not_bio() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._extract_bio_from_meta(
            ("See Instagram photos and videos " "from Test (@test)")
        )
        is None
    )


def test_header_bio_stops_at_external_link() -> None:
    fetcher = make_fetcher()

    links = (
        ExternalLink(
            url=HttpUrl("https://takl.ink/" "setayeshmasjedii"),
            type=(ExternalLinkType.LINK_IN_BIO),
        ),
    )

    result = fetcher._extract_bio_from_header(
        username="setayeshmasjedii",
        display_name="ستایش مسجدی",
        header_text=(
            "setayeshmasjedii\n"
            "468K followers\n"
            "222 following\n"
            "331 posts\n"
            "ستایش مسجدی\n"
            "Self-makeup training\n"
            "میکاپ آرتیست خودت باش\n"
            "takl.ink/setayeshmasjedii\n"
            "معرفی محصول\n"
        ),
        external_links=links,
    )

    assert result == ("Self-makeup training\n" "میکاپ آرتیست خودت باش")


def test_bio_stops_at_visible_domain_and_more() -> None:
    fetcher = make_fetcher()

    links = (
        ExternalLink(
            url=HttpUrl("https://www.lebaszirnikoo.ir"),
            type=ExternalLinkType.WEBSITE,
        ),
    )

    result = fetcher._extract_bio_from_header(
        username="lebaszirnikoo",
        display_name=("فروشگاه لباس زیر|لباس خواب"),
        header_text=(
            "lebaszirnikoo\n"
            "277K followers\n"
            "7 following\n"
            "2,187 posts\n"
            "فروشگاه لباس زیر|لباس خواب\n"
            "ثبت از دایرکت و بزودی سایت\n"
            "پیج لباس خواب:@nikoo.sleepwear\n"
            "پشتیبانی ۱۱ الی ۲۱\n"
            "www.lebaszirnikoo.ir and 1 more\n"
            "شورت\n"
            "بادی\n"
        ),
        external_links=links,
    )

    assert result == (
        "ثبت از دایرکت و بزودی سایت\n"
        "پیج لباس خواب:@nikoo.sleepwear\n"
        "پشتیبانی ۱۱ الی ۲۱"
    )


def test_bio_stops_at_real_highlight_title() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_bio_from_header(
        username="toys_kazemi",
        display_name=("فروشگاه اسباب بازی کاظمی آبادان"),
        header_text=(
            "toys_kazemi\n"
            "31K followers\n"
            "403 following\n"
            "821 posts\n"
            "فروشگاه اسباب بازی کاظمی آبادان\n"
            "🔆ما اینجا فقط اسباب بازی نمیفروشیم، شادی میفروشیم😍\n"
            "آبادان؛احمد اباد،۱۱فرعی،بین لین ۱ و ۲اصلی📍\n"
            "👇خرید راحت از سایت👇...\n"
            "کد رهگیری ۳\n"
            "عروسک جدید\n"
            "کد رهگیری ۲\n"
            "بسته های ارسالی\n"
        ),
        external_links=(),
        highlight_titles=(
            "کد رهگیری ۳",
            "عروسک جدید",
            "کد رهگیری ۲",
            "بسته های ارسالی",
        ),
    )

    assert result == (
        "🔆ما اینجا فقط اسباب بازی نمیفروشیم، شادی میفروشیم😍\n"
        "آبادان؛احمد اباد،۱۱فرعی،بین لین ۱ و ۲اصلی📍\n"
        "👇خرید راحت از سایت👇..."
    )


def test_bio_highlight_matching_normalizes_persian_characters() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_bio_from_header(
        username="test",
        display_name="Test",
        header_text=(
            "test\n"
            "10K followers\n"
            "1 following\n"
            "10 posts\n"
            "Test\n"
            "متن واقعی بایو\n"
            "كدرهگيری\n"
            "عنوان بعدی\n"
        ),
        external_links=(),
        highlight_titles=("کدرهگیری",),
    )

    assert result == "متن واقعی بایو"


def test_instagram_handle_is_not_visible_domain() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_visible_urls(
        text=("پیج لباس خواب:" "@nikoo.sleepwear"),
        username="lebaszirnikoo",
    )

    assert result == []


def test_partial_instagram_handle_is_not_extracted() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_visible_urls(
        text="@nikoo.sleepwear",
        username="lebaszirnikoo",
    )

    assert "https://ikoo.sleepwear" not in result

    assert result == []


def test_username_is_not_treated_as_website() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_visible_urls(
        text=("baneh.bosch\n" "فروشگاه لوازم خانگی"),
        username="baneh.bosch",
    )

    assert result == []


def test_real_visible_domain_is_extracted() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_visible_urls(
        text=("www.lebaszirnikoo.ir " "and 1 more"),
        username="lebaszirnikoo",
    )

    assert result == ["https://www.lebaszirnikoo.ir"]


def test_youtube_visible_url_is_extracted() -> None:
    fetcher = make_fetcher()

    result = fetcher._extract_visible_urls(
        text=("youtube.com/channel/" "UC123 and 1 more"),
        username="aliiiiiiiikarimi8",
    )

    assert "https://youtube.com/channel/UC123" in result


def test_canonical_url_key_deduplicates_trailing_slash() -> None:
    first = InstagramPlaywrightProfileFetcher._canonical_url_key("https://majazi.shop/")

    second = InstagramPlaywrightProfileFetcher._canonical_url_key("https://majazi.shop")

    assert first == second


def test_canonical_url_key_deduplicates_www() -> None:
    first = InstagramPlaywrightProfileFetcher._canonical_url_key(
        "https://www.example.com/"
    )

    second = InstagramPlaywrightProfileFetcher._canonical_url_key("https://example.com")

    assert first == second


def test_ali_bio_stops_before_youtube_and_more() -> None:
    fetcher = make_fetcher()

    links = (
        ExternalLink(
            url=HttpUrl("https://youtube.com/channel/test"),
            type=ExternalLinkType.YOUTUBE,
        ),
    )

    result = fetcher._extract_bio_from_header(
        username="aliiiiiiiikarimi8",
        display_name="Ali Karimi",
        header_text=(
            "aliiiiiiiikarimi8\n"
            "13.5M followers\n"
            "341 following\n"
            "846 posts\n"
            "Ali Karimi\n"
            "HumanRights💚🤍❤️\n"
            "youtube.com/channel/test and 1 more\n"
            "ايران💚🤍❤️\n"
            "اگاهى ، ازادى\n"
        ),
        external_links=links,
    )

    assert result == "HumanRights💚🤍❤️"


def test_instagram_redirect_is_unwrapped() -> None:
    result = InstagramPlaywrightProfileFetcher._unwrap_instagram_redirect(
        ("https://l.instagram.com/" "?u=https%3A%2F%2Fexample.com")
    )

    assert result == "https://example.com"


def test_instagram_is_not_external() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._is_external_url("https://instagram.com/test")
        is False
    )


def test_meta_footer_is_not_external() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._is_external_url("https://about.meta.com/")
        is False
    )


def test_regular_site_is_external() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._is_external_url("https://example.com/")
        is True
    )


def test_taklink_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://takl.ink/test")
        == ExternalLinkType.LINK_IN_BIO
    )


def test_zilink_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://zil.ink/test")
        == ExternalLinkType.LINK_IN_BIO
    )


def test_whatsapp_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://wa.me/98912")
        == ExternalLinkType.WHATSAPP
    )


def test_telegram_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://t.me/test")
        == ExternalLinkType.TELEGRAM
    )


def test_youtube_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type(
            "https://youtube.com/channel/UC123"
        )
        == ExternalLinkType.YOUTUBE
    )


def test_threads_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type(
            "https://www.threads.com/@test"
        )
        == ExternalLinkType.THREADS
    )


def test_twitter_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://twitter.com/test")
        == ExternalLinkType.TWITTER
    )


def test_x_type_is_twitter() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://x.com/test")
        == ExternalLinkType.TWITTER
    )


def test_google_maps_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type(
            "https://maps.app.goo.gl/test"
        )
        == ExternalLinkType.MAPS
    )


def test_regular_site_type() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._detect_link_type("https://example.com")
        == ExternalLinkType.WEBSITE
    )


def test_numeric_highlight_boundary() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._is_probable_highlight_boundary(
            line="4",
            bio_started=True,
        )
        is True
    )


def test_normal_text_is_not_highlight_boundary() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._is_probable_highlight_boundary(
            line="میکاپ روزانه",
            bio_started=True,
        )
        is False
    )


def test_normalize_username() -> None:
    assert (
        InstagramPlaywrightProfileFetcher._normalize_username(" @SetayeshMasjedii ")
        == "setayeshmasjedii"
    )
