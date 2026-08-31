from pydantic import HttpUrl
from app.crawler.playwright_scraper import (
    InstagramPlaywrightProfileFetcher,
)
from app.models.external_link import (
    ExternalLinkType,
)


def make_fetcher() -> InstagramPlaywrightProfileFetcher:
    return InstagramPlaywrightProfileFetcher()


def test_parse_compact_count_k() -> None:
    result = InstagramPlaywrightProfileFetcher._parse_compact_count("468K")

    assert result == 468_000


def test_parse_compact_count_m() -> None:
    result = InstagramPlaywrightProfileFetcher._parse_compact_count("1.5M")

    assert result == 1_500_000


def test_parse_compact_count_plain_integer() -> None:
    result = InstagramPlaywrightProfileFetcher._parse_compact_count("331")

    assert result == 331


def test_extract_count_from_description() -> None:
    fetcher = make_fetcher()

    description = "331 posts, " "468K followers, " "222 following"

    followers = fetcher._extract_count(
        text=description,
        label="followers",
    )

    following = fetcher._extract_count(
        text=description,
        label="following",
    )

    posts = fetcher._extract_count(
        text=description,
        label="posts",
    )

    assert followers == 468_000
    assert following == 222
    assert posts == 331


def test_clean_unicode_text_removes_directional_marks() -> None:
    raw = "\u200e" "ستایش مسجدی" "\u200f"

    result = InstagramPlaywrightProfileFetcher._clean_unicode_text(raw)

    assert result == "ستایش مسجدی"


def test_parse_display_name_removes_instagram_suffix() -> None:
    result = InstagramPlaywrightProfileFetcher._parse_display_name(
        ("ستایش مسجدی | setayeshmasjedi " "(@setayeshmasjedii) • Instagram")
    )

    assert result == "ستایش مسجدی | setayeshmasjedi"


def test_meta_boilerplate_is_not_used_as_bio() -> None:
    result = InstagramPlaywrightProfileFetcher._extract_bio_from_meta(
        ("See Instagram photos and videos " "from Test User (@test)")
    )

    assert result is None


def test_real_meta_bio_can_be_extracted() -> None:
    result = InstagramPlaywrightProfileFetcher._extract_bio_from_meta(
        ("10K Followers, 120 Following, " '50 Posts - "Beauty shop and makeup"')
    )

    assert result == "Beauty shop and makeup"


def test_header_bio_stops_at_external_link() -> None:
    fetcher = make_fetcher()

    header_text = (
        "setayeshmasjedii\n"
        "468K followers\n"
        "222 following\n"
        "331 posts\n"
        "ستایش مسجدی | setayeshmasjedi\n"
        "Self-makeup training | content creator💄✨\n"
        "میکاپ آرتیست خودت باش ❤️\n"
        "takl.ink/setayeshmasjedii\n"
        "معرفى محصول\n"
        "خرید از سایت\n"
        "دوره خودآرایی\n"
    )

    external_links = (fetcher._detect_link_type("https://takl.ink/setayeshmasjedii"),)

    # external_links در متد اصلی باید ExternalLink باشند،
    # پس این تست را با آبجکت واقعی می‌سازیم.
    from app.models.external_link import ExternalLink

    links = (
        ExternalLink(
            url=HttpUrl("https://takl.ink/setayeshmasjedii"),
            type=ExternalLinkType.LINK_IN_BIO,
        ),
    )

    result = fetcher._extract_bio_from_header(
        username="setayeshmasjedii",
        display_name=("ستایش مسجدی | setayeshmasjedi"),
        header_text=header_text,
        external_links=links,
    )

    assert result == (
        "Self-makeup training | content creator💄✨\n" "میکاپ آرتیست خودت باش ❤️"
    )


def test_stat_lines_are_detected() -> None:
    fetcher = make_fetcher()

    assert fetcher._is_stat_line("468k followers")

    assert fetcher._is_stat_line("222 following")

    assert fetcher._is_stat_line("331 posts")


def test_regular_bio_line_is_not_stat_line() -> None:
    fetcher = make_fetcher()

    assert not fetcher._is_stat_line("میکاپ آرتیست خودت باش")


def test_instagram_redirect_is_unwrapped() -> None:
    result = InstagramPlaywrightProfileFetcher._unwrap_instagram_redirect(
        ("https://l.instagram.com/" "?u=https%3A%2F%2Fexample.com%2Fshop")
    )

    assert result == ("https://example.com/shop")


def test_normal_external_url_is_not_modified() -> None:
    url = "https://example.com/shop"

    result = InstagramPlaywrightProfileFetcher._unwrap_instagram_redirect(url)

    assert result == url


def test_instagram_url_is_not_external() -> None:
    result = InstagramPlaywrightProfileFetcher._is_external_url(
        "https://www.instagram.com/test/"
    )

    assert result is False


def test_meta_footer_url_is_not_external() -> None:
    result = InstagramPlaywrightProfileFetcher._is_external_url(
        "https://about.meta.com/"
    )

    assert result is False


def test_facebook_footer_url_is_not_external() -> None:
    result = InstagramPlaywrightProfileFetcher._is_external_url(
        "https://www.facebook.com/help/"
    )

    assert result is False


def test_normal_website_is_external() -> None:
    result = InstagramPlaywrightProfileFetcher._is_external_url("https://example.com")

    assert result is True


def test_taklink_is_detected_as_link_in_bio() -> None:
    result = InstagramPlaywrightProfileFetcher._detect_link_type(
        "https://takl.ink/example"
    )

    assert result == ExternalLinkType.LINK_IN_BIO


def test_linktree_is_detected_as_link_in_bio() -> None:
    result = InstagramPlaywrightProfileFetcher._detect_link_type(
        "https://linktr.ee/example"
    )

    assert result == ExternalLinkType.LINK_IN_BIO


def test_whatsapp_is_detected() -> None:
    result = InstagramPlaywrightProfileFetcher._detect_link_type(
        "https://wa.me/989121234567"
    )

    assert result == ExternalLinkType.WHATSAPP


def test_telegram_is_detected() -> None:
    result = InstagramPlaywrightProfileFetcher._detect_link_type("https://t.me/example")

    assert result == ExternalLinkType.TELEGRAM


def test_regular_site_is_detected_as_website() -> None:
    result = InstagramPlaywrightProfileFetcher._detect_link_type("https://example.com")

    assert result == ExternalLinkType.WEBSITE


def test_numeric_highlight_can_be_boundary_after_bio() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._is_probable_highlight_boundary(
            line="4",
            bio_started=True,
        )
        is True
    )


def test_numeric_line_is_not_boundary_before_bio() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._is_probable_highlight_boundary(
            line="4",
            bio_started=False,
        )
        is False
    )


def test_normal_text_is_not_highlight_boundary() -> None:
    fetcher = make_fetcher()

    assert (
        fetcher._is_probable_highlight_boundary(
            line="میکاپ آرتیست خودت باش",
            bio_started=True,
        )
        is False
    )


def test_normalize_username() -> None:
    result = InstagramPlaywrightProfileFetcher._normalize_username(
        "  @SetayeshMasjedii  "
    )

    assert result == "setayeshmasjedii"
