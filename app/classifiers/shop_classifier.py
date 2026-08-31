import re
from dataclasses import dataclass
from enum import StrEnum

from app.models.external_link import ExternalLinkType
from app.models.profile import InstagramProfile


class ShopVerdict(StrEnum):
    SHOP = "shop"
    NOT_SHOP = "not_shop"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ShopClassification:
    verdict: ShopVerdict
    score: float
    matched_signals: tuple[str, ...]


class ShopClassifier:
    """
    Evidence-based shop classifier.

    Existing score behaviour is intentionally preserved.

    Additional evidence is added conservatively so existing profiles/tests
    do not change unexpectedly.
    """

    _SIGNAL_WEIGHTS: dict[str, float] = {
        "فروشگاه": 0.40,
        "ثبت سفارش": 0.40,
        "سفارش": 0.30,
        "خرید": 0.30,
        "فروش": 0.25,
        "قیمت": 0.20,
        "ارسال": 0.20,
        "محصول": 0.08,
        "کالا": 0.15,
        "دایرکت": 0.08,
        "شاپ": 0.30,
        "shop": 0.30,
        "store": 0.30,
        "order": 0.30,
        "shipping": 0.20,
    }

    _PREFIX_SIGNALS: frozenset[str] = frozenset(
        {
            "ثبت سفارش",
            "سفارش",
            "دایرکت",
            "محصول",
        }
    )

    _COMMERCIAL_SIGNALS: frozenset[str] = frozenset(
        {
            "فروشگاه",
            "ثبت سفارش",
            "سفارش",
            "خرید",
            "فروش",
            "قیمت",
            "محصول",
            "کالا",
            "شاپ",
            "shop",
            "store",
            "order",
        }
    )

    _FULFILLMENT_SIGNALS: tuple[str, ...] = (
        "ارسال",
        "تحویل",
        "ارسال فوری",
        "تحویل فوری",
        "پست",
        "تیپاکس",
        "shipping",
        "delivery",
    )

    _SOCIAL_SALES_LINK_TYPES: frozenset[ExternalLinkType] = frozenset(
        {
            ExternalLinkType.TELEGRAM,
            ExternalLinkType.WHATSAPP,
            ExternalLinkType.INSTAGRAM,
        }
    )

    def classify(
        self,
        profile: InstagramProfile,
    ) -> ShopClassification:
        bio = self._normalize_text(profile.bio or "")

        display_name = self._normalize_text(profile.display_name or "")

        combined_text = self._normalize_text(f"{display_name} {bio}")

        bio_signals = self._find_weighted_signals(bio)

        display_name_signals = self._find_weighted_signals(display_name)

        bio_signals = self._apply_signal_dominance(bio_signals)

        display_name_signals = self._apply_signal_dominance(display_name_signals)

        score = 0.0

        matched_signals: list[str] = []

        # Bio evidence receives full weight.
        for signal in bio_signals:
            score += self._SIGNAL_WEIGHTS[signal]

            if signal not in matched_signals:
                matched_signals.append(signal)

        # Display-name evidence receives half weight.
        for signal in display_name_signals:
            score += self._SIGNAL_WEIGHTS[signal] * 0.5

            if signal not in matched_signals:
                matched_signals.append(signal)

        has_commercial_signal = any(
            self._contains_signal(
                text=combined_text,
                signal=signal,
            )
            for signal in self._COMMERCIAL_SIGNALS
        )

        has_fulfillment_signal = any(
            self._contains_signal(
                text=bio,
                signal=signal,
            )
            for signal in self._FULFILLMENT_SIGNALS
        )

        has_external_link = bool(profile.external_links)

        has_social_sales_link = any(
            link.type in self._SOCIAL_SALES_LINK_TYPES
            for link in profile.external_links
        )

        has_purchase_signal_in_bio = self._contains_signal(
            text=bio,
            signal="خرید",
        )

        has_strong_commercial_name = self._has_strong_commercial_display_name(
            display_name_signals
        )

        # Preserve previous rule:
        #
        # فروش (.25) + ارسال (.20) + combination (.20)
        # = .65
        if self._has_sales_or_purchase_signal(bio) and has_fulfillment_signal:
            score += 0.20

        # Commercial profile + external destination.
        #
        # Example jjpoosh:
        # ثبت سفارش = .40
        # دایرکت = .08
        # external commercial link = .20
        # total = .68
        if has_external_link and has_commercial_signal:
            score += 0.20

        # Strong commercial display name together with
        # an external destination.
        if has_external_link and has_strong_commercial_name:
            score += 0.17

        # Purchase + fulfillment + direct social sales channel.
        #
        # Example:
        # خرید + تحویل + Telegram
        #
        # The social link alone does not imply shop.
        if (
            has_purchase_signal_in_bio
            and has_fulfillment_signal
            and has_social_sales_link
        ):
            score += 0.15

        # Strong commercial identity in the profile name plus
        # explicit purchase intent in the real bio.
        #
        # Example:
        #
        # Name:
        # فروشگاه اسباب بازی کاظمی آبادان
        #
        # Bio:
        # خرید راحت از سایت
        #
        # فروشگاه in name = .20
        # خرید in bio      = .30
        # combination      = .10
        # -----------------------
        # total            = .60
        #
        # This is intentionally narrow:
        # the bonus requires purchase intent in the BIO,
        # not merely another commercial word in the name.
        if has_strong_commercial_name and has_purchase_signal_in_bio:
            score += 0.10

        score = min(
            1.0,
            round(
                score,
                10,
            ),
        )

        if score >= 0.60:
            verdict = ShopVerdict.SHOP

        elif score <= 0.15:
            verdict = ShopVerdict.NOT_SHOP

        else:
            verdict = ShopVerdict.UNKNOWN

        return ShopClassification(
            verdict=verdict,
            score=score,
            matched_signals=tuple(matched_signals),
        )

    def _find_weighted_signals(
        self,
        text: str,
    ) -> list[str]:
        return [
            signal
            for signal in self._SIGNAL_WEIGHTS
            if self._contains_signal(
                text=text,
                signal=signal,
            )
        ]

    @staticmethod
    def _apply_signal_dominance(
        signals: list[str],
    ) -> list[str]:
        result = list(signals)

        if "فروشگاه" in result and "فروش" in result:
            result.remove("فروش")

        if "ثبت سفارش" in result and "سفارش" in result:
            result.remove("سفارش")

        return result

    def _has_sales_or_purchase_signal(
        self,
        text: str,
    ) -> bool:
        return any(
            self._contains_signal(
                text=text,
                signal=signal,
            )
            for signal in (
                "فروش",
                "خرید",
                "shop",
                "store",
                "order",
            )
        )

    @staticmethod
    def _has_strong_commercial_display_name(
        signals: list[str],
    ) -> bool:
        strong_signals = {
            "فروشگاه",
            "شاپ",
            "shop",
            "store",
        }

        return any(signal in strong_signals for signal in signals)

    def _contains_signal(
        self,
        *,
        text: str,
        signal: str,
    ) -> bool:
        normalized_signal = self._normalize_text(signal)

        if normalized_signal in self._PREFIX_SIGNALS:
            pattern = rf"(?<![\w])" rf"{re.escape(normalized_signal)}"

        else:
            pattern = rf"(?<![\w])" rf"{re.escape(normalized_signal)}" rf"(?![\w])"

        return (
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        translation_table = str.maketrans(
            {
                "ي": "ی",
                "ى": "ی",
                "ك": "ک",
                "ۀ": "ه",
                "ة": "ه",
                "\u200c": " ",
                "\u200f": "",
                "\u200e": "",
            }
        )

        normalized = value.translate(translation_table).lower()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()
