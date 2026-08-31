from app.classifiers.link_classifier import (
    LinkClassifier,
)
from app.models.external_link import (
    ExternalLinkType,
)


def test_regular_website() -> None:
    assert LinkClassifier.classify("https://example.com") == ExternalLinkType.WEBSITE


def test_instagram() -> None:
    assert (
        LinkClassifier.classify("https://instagram.com/test")
        == ExternalLinkType.INSTAGRAM
    )


def test_threads() -> None:
    assert (
        LinkClassifier.classify("https://threads.com/@test") == ExternalLinkType.THREADS
    )


def test_twitter() -> None:
    assert (
        LinkClassifier.classify("https://twitter.com/test") == ExternalLinkType.TWITTER
    )


def test_x_is_twitter() -> None:
    assert LinkClassifier.classify("https://x.com/test") == ExternalLinkType.TWITTER


def test_youtube() -> None:
    assert (
        LinkClassifier.classify("https://youtube.com/channel/UC123")
        == ExternalLinkType.YOUTUBE
    )


def test_youtu_be() -> None:
    assert LinkClassifier.classify("https://youtu.be/test") == ExternalLinkType.YOUTUBE


def test_linkedin() -> None:
    assert (
        LinkClassifier.classify("https://linkedin.com/in/test")
        == ExternalLinkType.LINKEDIN
    )


def test_facebook() -> None:
    assert (
        LinkClassifier.classify("https://facebook.com/test")
        == ExternalLinkType.FACEBOOK
    )


def test_tiktok() -> None:
    assert (
        LinkClassifier.classify("https://tiktok.com/@test") == ExternalLinkType.TIKTOK
    )


def test_pinterest() -> None:
    assert (
        LinkClassifier.classify("https://pinterest.com/test")
        == ExternalLinkType.PINTEREST
    )


def test_pin_it_is_pinterest() -> None:
    assert LinkClassifier.classify("https://pin.it/test") == ExternalLinkType.PINTEREST


def test_snapchat() -> None:
    assert (
        LinkClassifier.classify("https://snapchat.com/add/test")
        == ExternalLinkType.SNAPCHAT
    )


def test_telegram() -> None:
    assert LinkClassifier.classify("https://t.me/test") == ExternalLinkType.TELEGRAM


def test_whatsapp_wa_me() -> None:
    assert (
        LinkClassifier.classify("https://wa.me/989121234567")
        == ExternalLinkType.WHATSAPP
    )


def test_whatsapp_channel() -> None:
    assert (
        LinkClassifier.classify("https://whatsapp.com/channel/test")
        == ExternalLinkType.WHATSAPP
    )


def test_taklink() -> None:
    assert (
        LinkClassifier.classify("https://takl.ink/test") == ExternalLinkType.LINK_IN_BIO
    )


def test_zilink() -> None:
    assert (
        LinkClassifier.classify("https://zil.ink/test") == ExternalLinkType.LINK_IN_BIO
    )


def test_linktree() -> None:
    assert (
        LinkClassifier.classify("https://linktr.ee/test")
        == ExternalLinkType.LINK_IN_BIO
    )


def test_google_maps_short_link() -> None:
    assert (
        LinkClassifier.classify("https://maps.app.goo.gl/test") == ExternalLinkType.MAPS
    )


def test_google_maps_url() -> None:
    assert (
        LinkClassifier.classify("https://www.google.com/maps/place/Test")
        == ExternalLinkType.MAPS
    )


def test_map_title_can_identify_maps() -> None:
    assert (
        LinkClassifier.classify(
            "https://example.com/location",
            title="آدرس در گوگل مپ",
        )
        == ExternalLinkType.MAPS
    )
