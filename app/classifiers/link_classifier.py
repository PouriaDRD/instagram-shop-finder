from urllib.parse import urlparse

from app.models.external_link import ExternalLinkType


class LinkClassifier:
    LINK_IN_BIO_HOSTS = {
        "takl.ink",
        "linktr.ee",
        "zil.ink",
        "bio.link",
        "beacons.ai",
        "campsite.bio",
        "lnk.bio",
        "hoo.be",
        "solo.to",
        "msha.ke",
        "taplink.cc",
    }

    @staticmethod
    def classify(
        url: str,
        title: str | None = None,
    ) -> ExternalLinkType:
        normalized_url = url.strip().lower()

        normalized_title = title.strip().lower() if title else ""

        parsed = urlparse(normalized_url)

        hostname = (parsed.hostname or "").lower()

        hostname = hostname.removeprefix("www.")

        if LinkClassifier._is_instagram(hostname):
            return ExternalLinkType.INSTAGRAM

        if LinkClassifier._is_threads(hostname):
            return ExternalLinkType.THREADS

        if LinkClassifier._is_twitter(hostname):
            return ExternalLinkType.TWITTER

        if LinkClassifier._is_youtube(hostname):
            return ExternalLinkType.YOUTUBE

        if LinkClassifier._is_linkedin(hostname):
            return ExternalLinkType.LINKEDIN

        if LinkClassifier._is_facebook(hostname):
            return ExternalLinkType.FACEBOOK

        if LinkClassifier._is_tiktok(hostname):
            return ExternalLinkType.TIKTOK

        if LinkClassifier._is_pinterest(hostname):
            return ExternalLinkType.PINTEREST

        if LinkClassifier._is_snapchat(hostname):
            return ExternalLinkType.SNAPCHAT

        if LinkClassifier._is_whatsapp(
            hostname=hostname,
            normalized_url=normalized_url,
            normalized_title=normalized_title,
        ):
            return ExternalLinkType.WHATSAPP

        if LinkClassifier._is_telegram(
            hostname=hostname,
            normalized_title=normalized_title,
        ):
            return ExternalLinkType.TELEGRAM

        if LinkClassifier._is_maps(
            hostname=hostname,
            normalized_url=normalized_url,
            normalized_title=normalized_title,
        ):
            return ExternalLinkType.MAPS

        if hostname in LinkClassifier.LINK_IN_BIO_HOSTS:
            return ExternalLinkType.LINK_IN_BIO

        if LinkClassifier._looks_like_shop(normalized_title):
            return ExternalLinkType.SHOP

        if hostname:
            return ExternalLinkType.WEBSITE

        return ExternalLinkType.OTHER

    @staticmethod
    def _is_instagram(
        hostname: str,
    ) -> bool:
        return hostname == "instagram.com"

    @staticmethod
    def _is_threads(
        hostname: str,
    ) -> bool:
        return hostname == "threads.com"

    @staticmethod
    def _is_twitter(
        hostname: str,
    ) -> bool:
        return hostname in {
            "twitter.com",
            "x.com",
        }

    @staticmethod
    def _is_youtube(
        hostname: str,
    ) -> bool:
        return hostname in {
            "youtube.com",
            "youtu.be",
            "youtube-nocookie.com",
        }

    @staticmethod
    def _is_linkedin(
        hostname: str,
    ) -> bool:
        return hostname == "linkedin.com"

    @staticmethod
    def _is_facebook(
        hostname: str,
    ) -> bool:
        return hostname in {
            "facebook.com",
            "fb.com",
            "m.facebook.com",
        }

    @staticmethod
    def _is_tiktok(
        hostname: str,
    ) -> bool:
        return hostname == "tiktok.com"

    @staticmethod
    def _is_pinterest(
        hostname: str,
    ) -> bool:
        return hostname in {
            "pinterest.com",
            "pin.it",
        }

    @staticmethod
    def _is_snapchat(
        hostname: str,
    ) -> bool:
        return hostname == "snapchat.com"

    @staticmethod
    def _is_whatsapp(
        *,
        hostname: str,
        normalized_url: str,
        normalized_title: str,
    ) -> bool:
        return (
            hostname
            in {
                "wa.me",
                "whatsapp.com",
                "api.whatsapp.com",
            }
            or "whatsapp" in normalized_url
            or "whatsapp" in normalized_title
            or "واتساپ" in normalized_title
        )

    @staticmethod
    def _is_telegram(
        *,
        hostname: str,
        normalized_title: str,
    ) -> bool:
        return (
            hostname
            in {
                "t.me",
                "telegram.me",
                "telegram.org",
            }
            or "telegram" in normalized_title
            or "تلگرام" in normalized_title
        )

    @staticmethod
    def _is_maps(
        *,
        hostname: str,
        normalized_url: str,
        normalized_title: str,
    ) -> bool:
        if hostname in {
            "maps.app.goo.gl",
            "maps.google.com",
        }:
            return True

        if hostname == "google.com" and "/maps" in normalized_url:
            return True

        return any(
            signal in normalized_title
            for signal in (
                "google map",
                "google maps",
                "گوگل مپ",
                "نقشه",
                "آدرس روی نقشه",
                "ادرس روی نقشه",
            )
        )

    @staticmethod
    def _looks_like_shop(
        normalized_title: str,
    ) -> bool:
        return any(
            signal in normalized_title
            for signal in (
                "فروشگاه",
                "خرید",
                "shop",
                "store",
            )
        )
