import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import InstagramProfile


class ShopVerdict(StrEnum):
    SHOP = "shop"
    NOT_SHOP = "not_shop"
    UNKNOWN = "unknown"


class ShopClassificationResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    verdict: ShopVerdict

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    matched_signals: tuple[str, ...] = ()


class ShopClassifier:
    """
    Lightweight rule-based shop classifier.

    Design principles:
    - Bio is the primary source of commercial intent.
    - Display name is only supporting evidence.
    - Signals are canonicalized to prevent double counting.
    - Persian morphological variants can map to the same signal.
    """

    _SIGNAL_WEIGHTS: dict[str, float] = {
        # Strong commercial intent
        "فروشگاه": 0.45,
        "فروش": 0.35,
        "سفارش": 0.30,
        "خرید": 0.30,
        # Transaction signals
        "قیمت": 0.20,
        "موجودی": 0.20,
        # Fulfillment
        "ارسال": 0.15,
        # English commercial intent
        "shop": 0.35,
        "store": 0.35,
        "order": 0.30,
        "shipping": 0.15,
        # Supporting signals
        "دایرکت": 0.08,
        "واتساپ": 0.10,
        "whatsapp": 0.10,
        "تومان": 0.10,
        "محصول": 0.08,
        "کالا": 0.08,
    }

    _SIGNAL_ALIASES: dict[
        str,
        tuple[str, ...],
    ] = {
        "فروشگاه": (
            "فروشگاه",
            "فروشگاه‌ها",
            "فروشگاهها",
        ),
        "فروش": ("فروش",),
        "سفارش": (
            "سفارش",
            "سفارشات",
        ),
        "خرید": ("خرید",),
        "قیمت": (
            "قیمت",
            "قیمت‌ها",
            "قیمتها",
        ),
        "موجودی": ("موجودی",),
        "ارسال": ("ارسال",),
        "shop": ("shop",),
        "store": ("store",),
        "order": (
            "order",
            "orders",
        ),
        "shipping": ("shipping",),
        "دایرکت": ("دایرکت",),
        "واتساپ": ("واتساپ",),
        "whatsapp": ("whatsapp",),
        "تومان": ("تومان",),
        "محصول": (
            "محصول",
            "محصولات",
        ),
        "کالا": (
            "کالا",
            "کالاها",
            "کالاهای",
        ),
    }

    _COMMERCIAL_SIGNALS: frozenset[str] = frozenset(
        {
            "فروشگاه",
            "فروش",
            "سفارش",
            "خرید",
            "shop",
            "store",
            "order",
        }
    )

    _FULFILLMENT_SIGNALS: frozenset[str] = frozenset(
        {
            "ارسال",
            "shipping",
        }
    )

    _TRANSACTION_SIGNALS: frozenset[str] = frozenset(
        {
            "قیمت",
            "موجودی",
            "تومان",
        }
    )

    _DISPLAY_NAME_WEIGHT_FACTOR: float = 0.5

    def classify(
        self,
        profile: InstagramProfile,
    ) -> ShopClassificationResult:
        bio_text = self._normalize_text(profile.bio)

        display_name_text = self._normalize_text(profile.display_name)

        bio_signals = self._find_matches(bio_text)

        display_name_signals = self._find_matches(display_name_text)

        scored_signals = self._select_scored_signals(
            bio_signals=bio_signals,
            display_name_signals=display_name_signals,
        )

        score = self._calculate_score(
            bio_signals=bio_signals,
            display_name_signals=display_name_signals,
            scored_signals=scored_signals,
        )

        verdict = self._resolve_verdict(score)

        return ShopClassificationResult(
            verdict=verdict,
            score=score,
            matched_signals=scored_signals,
        )

    @staticmethod
    def _normalize_text(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        return value.strip().lower()

    def _find_matches(
        self,
        text: str,
    ) -> tuple[str, ...]:
        if not text:
            return ()

        matched: list[str] = []

        for canonical_signal, aliases in self._SIGNAL_ALIASES.items():
            if self._any_alias_exists(
                text=text,
                aliases=aliases,
            ):
                matched.append(canonical_signal)

        return tuple(matched)

    def _any_alias_exists(
        self,
        *,
        text: str,
        aliases: tuple[str, ...],
    ) -> bool:
        return any(
            self._signal_exists(
                text=text,
                signal=alias,
            )
            for alias in aliases
        )

    @staticmethod
    def _signal_exists(
        *,
        text: str,
        signal: str,
    ) -> bool:
        escaped_signal = re.escape(signal)

        pattern = rf"(?<!\w)" rf"{escaped_signal}" rf"(?!\w)"

        return (
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    def _select_scored_signals(
        self,
        *,
        bio_signals: tuple[str, ...],
        display_name_signals: tuple[str, ...],
    ) -> tuple[str, ...]:
        """
        Bio has priority.

        If the bio already contains commercial intent, display-name
        commercial words such as "Shop" are not counted again.

        This prevents:
            "Beauty Shop"
            +
            "فروش ... ارسال ..."

        from artificially reaching 100%.
        """

        bio_has_commercial_intent = bool(set(bio_signals) & self._COMMERCIAL_SIGNALS)

        if bio_has_commercial_intent:
            return bio_signals

        combined: list[str] = list(bio_signals)

        for signal in display_name_signals:
            if signal not in combined:
                combined.append(signal)

        return tuple(combined)

    def _calculate_score(
        self,
        *,
        bio_signals: tuple[str, ...],
        display_name_signals: tuple[str, ...],
        scored_signals: tuple[str, ...],
    ) -> float:
        bio_signal_set = set(bio_signals)

        display_signal_set = set(display_name_signals)

        score = 0.0

        for signal in scored_signals:
            weight = self._SIGNAL_WEIGHTS[signal]

            if signal in bio_signal_set:
                score += weight
                continue

            if signal in display_signal_set:
                score += weight * self._DISPLAY_NAME_WEIGHT_FACTOR

        score += self._calculate_combo_bonus(bio_signals)

        return min(
            round(
                score,
                2,
            ),
            1.0,
        )

    def _calculate_combo_bonus(
        self,
        bio_signals: tuple[str, ...],
    ) -> float:
        """
        Combo bonuses are intentionally based on BIO only.

        Display-name words should not create strong commercial
        confidence by themselves.
        """

        matched = set(bio_signals)

        bonus = 0.0

        has_commercial = bool(matched & self._COMMERCIAL_SIGNALS)

        has_fulfillment = bool(matched & self._FULFILLMENT_SIGNALS)

        has_transaction = bool(matched & self._TRANSACTION_SIGNALS)

        if has_commercial and has_fulfillment:
            bonus += 0.15

        if has_commercial and has_transaction:
            bonus += 0.10

        commercial_count = len(matched & self._COMMERCIAL_SIGNALS)

        if commercial_count >= 2:
            bonus += 0.10

        return bonus

    @staticmethod
    def _resolve_verdict(
        score: float,
    ) -> ShopVerdict:
        if score >= 0.6:
            return ShopVerdict.SHOP

        if score <= 0.15:
            return ShopVerdict.NOT_SHOP

        return ShopVerdict.UNKNOWN
