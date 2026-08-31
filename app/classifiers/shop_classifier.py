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
    (external links), applying normalization, prefix signal matching, shadowed signal filtering,
    and category-specific synergy bonuses to calculate a confidence score.
    """

    # Base confidence weights for canonical keyword signals
    _SIGNAL_WEIGHTS: dict[str, float] = {
        "فروشگاه": 0.45,
        "فروش": 0.35,
        "شاپ": 0.35,
        # Stronger intent signal than generic "سفارش"
        "ثبت سفارش": 0.40,
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
            "فروشگاه ها",
            "فروشگاه‌ها",
            "فروشگاهها",
        ),
        "فروش": ("فروش",),
        "شاپ": ("شاپ",),
        "ثبت سفارش": ("ثبت سفارش",),
        "سفارش": (
            "سفارش",
            "سفارشات",
        ),
        "خرید": ("خرید",),
        "قیمت": (
            "قیمت",
            "قیمت ها",
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

    # Signals allowed to match as prefixes without requiring right-side word boundaries
    # (handles attached Persian bio patterns like "ثبت سفارشسايت", "سفارشسايت" or "دايركتوحضوري")
    _PREFIX_MATCH_SIGNALS: frozenset[str] = frozenset(
        {
            "ثبت سفارش",
            "سفارش",
            "دایرکت",
        }
    )

    # Dominance mapping to suppress sub-keyword double counting
    # (e.g., "فروشگاه" suppresses "فروش", "ثبت سفارش" suppresses "سفارش")
    _DOMINANT_SIGNALS: dict[
        str,
        tuple[str, ...],
    ] = {
        "فروشگاه": ("فروش",),
        "ثبت سفارش": ("سفارش",),
    }

    # Direct intent keywords indicating commercial activity
    _COMMERCIAL_SIGNALS: frozenset[str] = frozenset(
        {
            "فروشگاه",
            "فروش",
            "شاپ",
            "ثبت سفارش",
            "سفارش",
            "خرید",
            "shop",
            "store",
            "order",
        }
    )

    # Keywords associated with shipping and delivery logistics
    _FULFILLMENT_SIGNALS: frozenset[str] = frozenset(
        {
            "ارسال",
            "shipping",
        }
    )

    # Keywords associated with pricing, currency, or inventory
    _TRANSACTION_SIGNALS: frozenset[str] = frozenset(
        {
            "قیمت",
            "موجودی",
            "تومان",
        }
    )

    # Weight discount factor for signals matched in display name instead of bio
    _DISPLAY_NAME_WEIGHT_FACTOR = 0.5

    # Bonus applied when commercial profiles contain external website links
    _EXTERNAL_LINK_BONUS = 0.20

    # Bonus applied when commercial intent appears in both display name and bio
    _NAME_COMMERCIAL_SYNERGY_BONUS = 0.15

    # Additional bonus when display name features multiple commercial keywords with external link
    _MULTIPLE_NAME_COMMERCIAL_BONUS = 0.15

    def classify(
        self,
        profile: InstagramProfile,
    ) -> ShopClassificationResult:
        """Evaluates an Instagram profile and classifies whether it operates as an e-commerce shop.

        Args:
            profile: Target InstagramProfile instance containing bio and display name fields.

        Returns:
            A ShopClassificationResult containing the verdict, confidence score, and matched signals.
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
        """Standardizes text by stripping whitespace, lowercasing, and replacing Persian character variants."""
        if not value:
            return ""

        normalized = (
            value.strip()
            .lower()
            .replace("ي", "ی")
            .replace("ى", "ی")
            .replace("ك", "ک")
            .replace("\u200c", " ")  # Replace half-spaces with standard spaces
            .replace("\u200f", "")  # Strip RTL mark
            .replace("\u200e", "")  # Strip LTR mark
        )

        # Collapse redundant whitespace gaps into single spaces
        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    def _find_matches(
        self,
        text: str,
    ) -> tuple[str, ...]:
        """Scans input text for recognized signal alias matches and strips shadowed sub-signals.

        Args:
            text: Normalized target text to search.

        Returns:
            Tuple of unique canonical signal strings matched in the text.
        """
        if not text:
            return ()

        matches: list[str] = []

        for canonical, aliases in self._SIGNAL_ALIASES.items():
            prefix_match = canonical in self._PREFIX_MATCH_SIGNALS

            if any(
                self._signal_exists(
                    text=text,
                    signal=alias,
                    allow_attached_suffix=prefix_match,
                )
                for alias in aliases
            ):
                matches.append(canonical)

        return self._remove_shadowed_signals(tuple(matches))

    @staticmethod
    def _signal_exists(
        *,
        text: str,
        signal: str,
        allow_attached_suffix: bool,
    ) -> bool:
        """Performs regex matching for a specific signal against text with optional suffix allowance."""
        normalized_signal = (
            signal.lower()
            .replace("ي", "ی")
            .replace("ى", "ی")
            .replace("ك", "ک")
            .replace("\u200c", " ")
        )

        escaped = re.escape(normalized_signal)

        if allow_attached_suffix:
            # Enforce left boundary only to support compound terms ("ثبت سفارشسايت", "دايركتوحضوري")
            pattern = rf"(?<!\w)" rf"{escaped}"
        else:
            # Enforce full word boundaries on both sides
            pattern = rf"(?<!\w)" rf"{escaped}" rf"(?!\w)"

        return (
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    def _remove_shadowed_signals(
        self,
        signals: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Filters out sub-signals that are subsumed by broader dominant signals.

        For example, removes 'فروش' when 'فروشگاه' is present, or 'سفارش' when 'ثبت سفارش' is present.
        """
        signal_set = set(signals)

        shadowed: set[str] = set()

        for dominant, children in self._DOMINANT_SIGNALS.items():
            if dominant not in signal_set:
                continue

            for child in children:
                if child in signal_set:
                    shadowed.add(child)

        return tuple(signal for signal in signals if signal not in shadowed)

    @staticmethod
    def _combine_signals(
        first: tuple[str, ...],
        second: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Merges two signal tuples while preserving insertion order and removing duplicates."""
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
        """Calculates total shop confidence score incorporating base signal weights and contextual bonuses."""
        score = 0.0

        # Accumulate primary bio signal weights
        for signal in bio_signals:
            score += self._SIGNAL_WEIGHTS[signal]

        # Accumulate discounted display name weights (skipped if signal was already matched in bio)
        for signal in display_name_signals:
            if signal in bio_signals:
                continue

            score += self._SIGNAL_WEIGHTS[signal] * self._DISPLAY_NAME_WEIGHT_FACTOR

        # Apply multi-signal combination and profile context bonuses
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
        """Calculates synergy bonuses when complementary signal types co-occur within the profile bio."""
        matched = set(bio_signals)

        bonus = 0.0

        has_commercial = bool(matched & self._COMMERCIAL_SIGNALS)

        has_fulfillment = bool(matched & self._FULFILLMENT_SIGNALS)

        has_transaction = bool(matched & self._TRANSACTION_SIGNALS)

        # Bonus for combining commercial intent with fulfillment/shipping info
        if has_commercial and has_fulfillment:
            bonus += 0.15

        # Bonus for combining commercial intent with transaction/pricing details
        if has_commercial and has_transaction:
            bonus += 0.10

        # Bonus for matching two or more distinct commercial keywords
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
        """Calculates bonuses based on cross-field synergies and profile features like external website links."""
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

        # Synergy bonus when display name contains commercial intent and bio provides supporting evidence
        if has_name_commercial and has_bio_evidence:
            bonus += self._NAME_COMMERCIAL_SYNERGY_BONUS

        # Bonus when external URL presence coincides with commercial keywords
        if has_external_link and has_any_commercial_evidence:
            bonus += self._EXTERNAL_LINK_BONUS

        # Additional bonus when external URL presence coincides with multiple commercial signals in display name
        if has_external_link and len(display_commercial_signals) >= 2:
            bonus += self._MULTIPLE_NAME_COMMERCIAL_BONUS

        return bonus

    @staticmethod
    def _resolve_verdict(
        score: float,
    ) -> ShopVerdict:
        """Maps final numerical confidence score to a categorical ShopVerdict enum value."""
        if score >= 0.6:
            return ShopVerdict.SHOP

        if score <= 0.15:
            return ShopVerdict.NOT_SHOP

        return ShopVerdict.UNKNOWN
