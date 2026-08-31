import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import InstagramProfile


class ShopVerdict(StrEnum):
    """Enumeration of categorical classification outcomes for shop identification.

    Attributes:
        SHOP: The profile is confidently identified as an e-commerce shop.
        NOT_SHOP: The profile lacks sufficient commercial signals and is classified as a non-shop.
        UNKNOWN: The profile contains ambiguous or weak signals falling between decision thresholds.
    """

    SHOP = "shop"
    NOT_SHOP = "not_shop"
    UNKNOWN = "unknown"


class ShopClassificationResult(BaseModel):
    """Immutable data model representing the output of shop profile classification.

    Attributes:
        verdict: Final categorical classification decision (SHOP, NOT_SHOP, or UNKNOWN).
        score: Calculated confidence score bounded between 0.0 and 1.0.
        matched_signals: Unique list of canonical keyword signals matched across bio and display name.
    """

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
    """Heuristic rule-based classifier for detecting commercial e-commerce Instagram profiles.

    Evaluates keyword signals across profile metadata (bio, display name) and structural signals
    (external links), applying category-specific synergy bonuses and multi-keyword name rules to
    produce a confidence score.
    """

    # Base confidence weights for canonical keyword signals
    _SIGNAL_WEIGHTS: dict[
        str,
        float,
    ] = {
        "فروشگاه": 0.45,
        "فروش": 0.35,
        "شاپ": 0.35,
        "سفارش": 0.30,
        "خرید": 0.30,
        "قیمت": 0.20,
        "موجودی": 0.20,
        "ارسال": 0.15,
        "shop": 0.35,
        "store": 0.35,
        "order": 0.30,
        "shipping": 0.15,
        "دایرکت": 0.08,
        "واتساپ": 0.10,
        "whatsapp": 0.10,
        "تومان": 0.10,
        "محصول": 0.08,
        "کالا": 0.08,
    }

    # Alias mapping for normalizing character variants and plural forms to canonical signals
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
        "شاپ": ("شاپ",),
        "سفارش": (
            "سفارش",
            "سفارشات",
        ),
        "خرید": (
            "خرید",
            "خريد",
        ),
        "قیمت": (
            "قیمت",
            "قيمت",
            "قیمت‌ها",
            "قیمتها",
        ),
        "موجودی": (
            "موجودی",
            "موجودي",
        ),
        "ارسال": ("ارسال",),
        "shop": ("shop",),
        "store": ("store",),
        "order": (
            "order",
            "orders",
        ),
        "shipping": ("shipping",),
        "دایرکت": (
            "دایرکت",
            "دايرکت",
            "دايركت",
        ),
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

    # Direct intent keywords indicating commercial activity
    _COMMERCIAL_SIGNALS = frozenset(
        {
            "فروشگاه",
            "فروش",
            "شاپ",
            "سفارش",
            "خرید",
            "shop",
            "store",
            "order",
        }
    )

    # Keywords associated with shipping and delivery logistics
    _FULFILLMENT_SIGNALS = frozenset(
        {
            "ارسال",
            "shipping",
        }
    )

    # Keywords associated with pricing, currency, or inventory
    _TRANSACTION_SIGNALS = frozenset(
        {
            "قیمت",
            "موجودی",
            "تومان",
        }
    )

    # Multiplier applied to signals found in display name rather than bio
    _DISPLAY_NAME_WEIGHT_FACTOR = 0.5

    # Bonus applied when a commercial profile features external website links
    _EXTERNAL_LINK_BONUS = 0.20

    # Bonus applied when commercial intent appears in both display name and bio
    _NAME_COMMERCIAL_SYNERGY_BONUS = 0.15

    # Additional bonus when display name contains multiple commercial signals along with an external link
    _MULTIPLE_NAME_COMMERCIAL_BONUS = 0.15

    def classify(
        self,
        profile: InstagramProfile,
    ) -> ShopClassificationResult:
        """Evaluates an Instagram profile and classifies whether it operates as an e-commerce shop.

        Args:
            profile: Target InstagramProfile instance containing metadata fields.

        Returns:
            A ShopClassificationResult with the verdict, confidence score, and matched signals.
        """
        bio_text = self._normalize_text(profile.bio)

        display_name_text = self._normalize_text(profile.display_name)

        bio_signals = self._find_matches(bio_text)

        display_name_signals = self._find_matches(display_name_text)

        matched_signals = self._combine_signals(
            bio_signals,
            display_name_signals,
        )

        score = self._calculate_score(
            profile=profile,
            bio_signals=bio_signals,
            display_name_signals=display_name_signals,
        )

        verdict = self._resolve_verdict(score)

        return ShopClassificationResult(
            verdict=verdict,
            score=score,
            matched_signals=matched_signals,
        )

    @staticmethod
    def _normalize_text(
        value: str | None,
    ) -> str:
        """Standardizes text strings by lowercasing and replacing Arabic character variants."""
        if not value:
            return ""

        return value.strip().lower().replace("ي", "ی").replace("ك", "ک")

    def _find_matches(
        self,
        text: str,
    ) -> tuple[str, ...]:
        """Scans input text for any recognized signal alias matches.

        Args:
            text: Normalized target text to search.

        Returns:
            Tuple of unique canonical signal strings matched in the text.
        """
        if not text:
            return ()

        matches: list[str] = []

        for canonical, aliases in self._SIGNAL_ALIASES.items():
            if any(
                self._signal_exists(
                    text=text,
                    signal=alias,
                )
                for alias in aliases
            ):
                matches.append(canonical)

        return tuple(matches)

    @staticmethod
    def _signal_exists(
        *,
        text: str,
        signal: str,
    ) -> bool:
        """Performs regex word boundary matching for a specific signal against text."""
        normalized_signal = signal.lower().replace("ي", "ی").replace("ك", "ک")

        escaped = re.escape(normalized_signal)

        # Negative lookbehind/lookahead to prevent partial word matching
        pattern = rf"(?<!\w)" rf"{escaped}" rf"(?!\w)"

        return (
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    @staticmethod
    def _combine_signals(
        first: tuple[str, ...],
        second: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Merges two signal tuples while preserving insertion order and deduplicating items."""
        combined: list[str] = []

        for signal in (
            *first,
            *second,
        ):
            if signal not in combined:
                combined.append(signal)

        return tuple(combined)

    def _calculate_score(
        self,
        *,
        profile: InstagramProfile,
        bio_signals: tuple[str, ...],
        display_name_signals: tuple[str, ...],
    ) -> float:
        """Calculates total shop confidence score including base weights and synergy bonuses."""
        score = 0.0

        # Primary bio signal scores
        for signal in bio_signals:
            score += self._SIGNAL_WEIGHTS[signal]

        # Secondary display name signal scores (discounted if already present in bio)
        for signal in display_name_signals:
            if signal in bio_signals:
                continue

            score += self._SIGNAL_WEIGHTS[signal] * self._DISPLAY_NAME_WEIGHT_FACTOR

        # Apply multi-signal combinations and profile context bonuses
        score += self._calculate_bio_combo_bonus(bio_signals)

        score += self._calculate_profile_context_bonus(
            profile=profile,
            bio_signals=bio_signals,
            display_name_signals=display_name_signals,
        )

        return min(
            round(
                score,
                2,
            ),
            1.0,
        )

    def _calculate_bio_combo_bonus(
        self,
        bio_signals: tuple[str, ...],
    ) -> float:
        """Calculates synergy bonuses when complementary signal types co-occur in the bio."""
        matched = set(bio_signals)

        bonus = 0.0

        has_commercial = bool(matched & self._COMMERCIAL_SIGNALS)

        has_fulfillment = bool(matched & self._FULFILLMENT_SIGNALS)

        has_transaction = bool(matched & self._TRANSACTION_SIGNALS)

        # Commercial intent + logistics evidence
        if has_commercial and has_fulfillment:
            bonus += 0.15

        # Commercial intent + transaction/pricing details
        if has_commercial and has_transaction:
            bonus += 0.10

        # Multiple strong commercial intent keywords in bio
        if len(matched & self._COMMERCIAL_SIGNALS) >= 2:
            bonus += 0.10

        return bonus

    def _calculate_profile_context_bonus(
        self,
        *,
        profile: InstagramProfile,
        bio_signals: tuple[str, ...],
        display_name_signals: tuple[str, ...],
    ) -> float:
        """Calculates bonuses based on cross-field synergies and profile features like external links."""
        bonus = 0.0

        bio_set = set(bio_signals)

        display_set = set(display_name_signals)

        bio_commercial_signals = bio_set & self._COMMERCIAL_SIGNALS

        display_commercial_signals = display_set & self._COMMERCIAL_SIGNALS

        has_name_commercial = bool(display_commercial_signals)

        has_bio_evidence = bool(bio_set)

        has_external_link = bool(profile.external_links)

        has_any_commercial_evidence = bool(
            bio_commercial_signals or display_commercial_signals
        )

        # Commercial display name paired with bio evidence
        if has_name_commercial and has_bio_evidence:
            bonus += self._NAME_COMMERCIAL_SYNERGY_BONUS

        # External URL paired with commercial keywords
        if has_external_link and has_any_commercial_evidence:
            bonus += self._EXTERNAL_LINK_BONUS

        # External URL paired with multiple commercial signals in display name
        if has_external_link and len(display_commercial_signals) >= 2:
            bonus += self._MULTIPLE_NAME_COMMERCIAL_BONUS

        return bonus

    @staticmethod
    def _resolve_verdict(
        score: float,
    ) -> ShopVerdict:
        """Maps final numerical score to a categorical ShopVerdict enum value."""
        if score >= 0.6:
            return ShopVerdict.SHOP

        if score <= 0.15:
            return ShopVerdict.NOT_SHOP

        return ShopVerdict.UNKNOWN
