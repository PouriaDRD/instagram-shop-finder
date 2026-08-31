import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)


class CategoryClassificationResult(BaseModel):
    """Immutable data model representing the output of profile category classification.

    Attributes:
        category: Predicted profile category enum value (e.g., BEAUTY, CLOTHING, UNKNOWN).
        score: Calculated category confidence score bounded between 0.0 and 1.0.
        matched_signals: Unique list of canonical keyword signals matched for the predicted category.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    category: ProfileCategory

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    matched_signals: tuple[str, ...] = ()


class CategoryClassifier:
    """Heuristic rule-based classifier for categorizing Instagram profiles into vertical domains.

    Scans profile metadata (display name, bio text) for category-specific keyword signals,
    handling Persian character normalization, half-spaces, and attached compound term prefixes.
    """

    # Dictionary mapping profile categories to canonical keywords and their variant aliases
    _CATEGORY_SIGNALS: dict[
        ProfileCategory,
        dict[str, tuple[str, ...]],
    ] = {
        ProfileCategory.BEAUTY: {
            "آرایشی": ("آرایشی",),
            "میکاپ": (
                "میکاپ",
                "makeup",
            ),
            "پوست": ("پوست",),
            "اسکین": (
                "اسکین",
                "skincare",
            ),
            "beauty": ("beauty",),
            "رژ": ("رژ",),
            "کرم": ("کرم",),
            "ریمل": ("ریمل",),
        },
        ProfileCategory.FASHION: {
            "فشن": (
                "فشن",
                "fashion",
            ),
            "استایل": (
                "استایل",
                "style",
            ),
            "مد": ("مد",),
        },
        ProfileCategory.CLOTHING: {
            "پوشاک": ("پوشاک",),
            "لباس": (
                "لباس",
                "لباس ها",
                "لباس‌های",
            ),
            "لباس زیر": ("لباس زیر",),
            "لباس خواب": ("لباس خواب",),
            "شورت": ("شورت",),
            "جوراب": ("جوراب",),
            "مانتو": ("مانتو",),
            "شومیز": ("شومیز",),
            "شلوار": ("شلوار",),
            "تیشرت": ("تیشرت",),
            "هودی": ("هودی",),
            "dress": ("dress",),
            "clothing": ("clothing",),
            "underwear": ("underwear",),
            "lingerie": ("lingerie",),
        },
        ProfileCategory.HOME: {
            "لوازم خانگی": ("لوازم خانگی",),
            "خانه": ("خانه",),
            "هوم": (
                "هوم",
                "home",
            ),
            "دکور": (
                "دکور",
                "decor",
            ),
            "دکوراسیون": ("دکوراسیون",),
            "آشپزخانه": ("آشپزخانه",),
            "ظروف": ("ظروف",),
            "جهیزیه": ("جهیزیه",),
        },
        ProfileCategory.ACCESSORIES: {
            "اکسسوری": (
                "اکسسوری",
                "accessory",
                "accessories",
            ),
            "زیورآلات": (
                "زیورآلات",
                "jewelry",
            ),
            "گردنبند": ("گردنبند",),
            "دستبند": ("دستبند",),
            "انگشتر": ("انگشتر",),
            "کیف": ("کیف",),
            "ساعت": ("ساعت",),
        },
    }

    # Signals allowed to match as prefixes without right-side word boundaries
    # (e.g., matching "شورت" in compound brand/specialty terms like "شورتولوژیست")
    _PREFIX_MATCH_SIGNALS: frozenset[str] = frozenset(
        {
            "شورت",
        }
    )

    # Base weight multiplier added per matched signal toward final category confidence score
    _SIGNAL_WEIGHT = 0.25

    def classify(
        self,
        profile: InstagramProfile,
    ) -> CategoryClassificationResult:
        """Evaluates an Instagram profile and classifies it into its primary domain category.

        Args:
            profile: Target InstagramProfile instance containing display name and bio text.

        Returns:
            A CategoryClassificationResult with the top category, confidence score, and matches.
        """
        text = self._build_searchable_text(profile)

        category_matches: dict[
            ProfileCategory,
            tuple[str, ...],
        ] = {}

        # Scan searchable text against all defined categories
        for category, signals in self._CATEGORY_SIGNALS.items():
            matches = self._find_category_matches(
                text=text,
                signals=signals,
            )

            category_matches[category] = matches

        best_category = ProfileCategory.UNKNOWN

        best_matches: tuple[str, ...] = ()

        # Select category with the highest count of matched signal keywords
        for category, matches in category_matches.items():
            if len(matches) > len(best_matches):
                best_category = category
                best_matches = matches

        # Return UNKNOWN if no category signals were identified
        if not best_matches:
            return CategoryClassificationResult(
                category=(ProfileCategory.UNKNOWN),
                score=0.0,
                matched_signals=(),
            )

        # Calculate capped confidence score based on total signal count
        score = min(
            round(
                len(best_matches) * self._SIGNAL_WEIGHT,
                2,
            ),
            1.0,
        )

        return CategoryClassificationResult(
            category=best_category,
            score=score,
            matched_signals=best_matches,
        )

    @classmethod
    def _build_searchable_text(
        cls,
        profile: InstagramProfile,
    ) -> str:
        """Combines profile display name and bio into a single normalized searchable string."""
        parts = (
            profile.display_name or "",
            profile.bio or "",
        )

        return cls._normalize_text(" ".join(parts))

    def _find_category_matches(
        self,
        *,
        text: str,
        signals: dict[
            str,
            tuple[str, ...],
        ],
    ) -> tuple[str, ...]:
        """Scans text for matches against a specific category's signal definitions.

        Args:
            text: Normalized target text to search.
            signals: Dictionary of canonical keyword signals and their alias tuples.

        Returns:
            Tuple of matched canonical signal strings for the category.
        """
        matches: list[str] = []

        for canonical, aliases in signals.items():
            allow_prefix = canonical in self._PREFIX_MATCH_SIGNALS

            if any(
                self._signal_exists(
                    text=text,
                    signal=alias,
                    allow_attached_suffix=allow_prefix,
                )
                for alias in aliases
            ):
                matches.append(canonical)

        return tuple(matches)

    @classmethod
    def _signal_exists(
        cls,
        *,
        text: str,
        signal: str,
        allow_attached_suffix: bool,
    ) -> bool:
        """Performs regex matching for a specific signal alias against text."""
        normalized_signal = cls._normalize_text(signal)

        escaped = re.escape(normalized_signal)

        if allow_attached_suffix:
            # Enforce left boundary only to support compound term matching
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

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """Standardizes text by lowercasing, replacing Persian variants, stripping diacritics and control marks."""
        value = (
            value.lower()
            .replace("ي", "ی")
            .replace("ى", "ی")
            .replace("ك", "ک")
            .replace("\u200c", " ")  # Replace half-space with standard space
            .replace("\u200f", "")  # Strip RTL mark
            .replace("\u200e", "")  # Strip LTR mark
        )

        # Strip combining marks (Mn) and formatting control characters (Cf)
        value = "".join(
            character
            for character in value
            if unicodedata.category(character)
            not in {
                "Mn",
                "Cf",
            }
        )

        # Collapse whitespace sequences into single spaces
        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()
