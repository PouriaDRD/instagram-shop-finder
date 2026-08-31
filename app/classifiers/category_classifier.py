import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import InstagramProfile, ProfileCategory


class CategoryClassificationResult(BaseModel):
    """Immutable data model representing the result of profile category classification.

    Attributes:
        category: Classified ProfileCategory enum value.
        score: Normalized classification confidence score between 0.0 and 1.0.
        matched_signals: Tuple of canonical keyword signal strings matched during classification.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    category: ProfileCategory
    score: float = Field(ge=0.0, le=1.0)
    matched_signals: tuple[str, ...] = ()


class CategoryClassifier:
    """Rule-based keyword classifier for assigning category labels to Instagram profiles."""

    # Map of category enums to dictionaries of canonical signal names and their string aliases
    _CATEGORY_SIGNALS: dict[
        ProfileCategory,
        dict[str, tuple[str, ...]],
    ] = {
        ProfileCategory.BEAUTY: {
            "آرایشی": ("آرایشی",),
            "میکاپ": (
                "میکاپ",
                "ميکاپ",
                "ميكاپ",
                "makeup",
            ),
            "پوست": ("پوست",),
            "اسکین": (
                "اسکین",
                "اسكين",
                "skincare",
            ),
            "beauty": ("beauty",),
            "رژ": ("رژ",),
            "کرم": (
                "کرم",
                "كرم",
            ),
            "ریمل": (
                "ریمل",
                "ريمل",
            ),
        },
        ProfileCategory.FASHION: {
            "فشن": (
                "فشن",
                "fashion",
            ),
            "استایل": (
                "استایل",
                "استايل",
                "style",
            ),
            "مد": ("مد",),
        },
        ProfileCategory.CLOTHING: {
            "پوشاک": (
                "پوشاک",
                "پوشاك",
            ),
            "لباس": (
                "لباس",
                "لباس‌ها",
                "لباسها",
                "لباس های",
                "لباس‌های",
            ),
            "مانتو": ("مانتو",),
            "شومیز": (
                "شومیز",
                "شوميز",
            ),
            "شلوار": ("شلوار",),
            "تیشرت": (
                "تیشرت",
                "تيشرت",
            ),
            "هودی": (
                "هودی",
                "هودي",
            ),
            "dress": ("dress",),
            "clothing": ("clothing",),
        },
        ProfileCategory.HOME: {
            "لوازم خانگی": (
                "لوازم خانگی",
                "لوازم خانگي",
            ),
            "خانه": ("خانه",),
            "هوم": (
                "هوم",
                "home",
            ),
            "دکور": (
                "دکور",
                "دكور",
                "decor",
            ),
            "دکوراسیون": (
                "دکوراسیون",
                "دكوراسيون",
            ),
            "آشپزخانه": ("آشپزخانه",),
            "ظروف": ("ظروف",),
            "جهیزیه": (
                "جهیزیه",
                "جهيزيه",
            ),
        },
        ProfileCategory.ACCESSORIES: {
            "اکسسوری": (
                "اکسسوری",
                "اكسسوری",
                "اكسسوري",
                "accessory",
                "accessories",
            ),
            "زیورآلات": (
                "زیورآلات",
                "زيورآلات",
                "jewelry",
            ),
            "گردنبند": ("گردنبند",),
            "دستبند": ("دستبند",),
            "انگشتر": ("انگشتر",),
            "کیف": (
                "کیف",
                "كيف",
            ),
            "ساعت": ("ساعت",),
        },
    }

    # Weight per unique signal match used when calculating confidence score
    _SIGNAL_WEIGHT = 0.25

    def classify(
        self,
        profile: InstagramProfile,
    ) -> CategoryClassificationResult:
        """Classifies an Instagram profile based on keyword signals in display name and bio.

        Args:
            profile: Target InstagramProfile model containing display name and bio text.

        Returns:
            A CategoryClassificationResult containing best matching category, score, and matched signals.
        """
        text = self._build_searchable_text(profile)

        category_matches: dict[
            ProfileCategory,
            tuple[str, ...],
        ] = {}

        # Evaluate keyword signals for each supported category
        for category, signals in self._CATEGORY_SIGNALS.items():
            matches = self._find_category_matches(
                text=text,
                signals=signals,
            )

            category_matches[category] = matches

        best_category = ProfileCategory.UNKNOWN
        best_matches: tuple[str, ...] = ()

        # Select category with highest count of unique signal matches
        for category, matches in category_matches.items():
            if len(matches) > len(best_matches):
                best_category = category
                best_matches = matches

        # Fallback for profiles without matching signals
        if not best_matches:
            return CategoryClassificationResult(
                category=ProfileCategory.UNKNOWN,
                score=0.0,
                matched_signals=(),
            )

        # Score increases linearly with match count, capped at 1.0
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
        """Concatenates and normalizes display name and bio fields for signal searching."""
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
        """Finds all canonical signals present in text by matching against alias list.

        Args:
            text: Normalized searchable string.
            signals: Dictionary mapping canonical signal names to alias tuple.

        Returns:
            Tuple of canonical signal names matched in text.
        """
        matches: list[str] = []

        for canonical, aliases in signals.items():
            if any(
                self._signal_exists(
                    text=text,
                    signal=alias,
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
    ) -> bool:
        """Checks if a normalized signal string exists as a distinct word in text using regex boundaries."""
        normalized_signal = cls._normalize_text(signal)
        escaped = re.escape(normalized_signal)

        # Word boundary assertion matching standalone terms
        pattern = rf"(?<!\w){escaped}(?!\w)"

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
        """Standardizes text string by lowercasing, replacing character variants, stripping diacritics and excess space.

        Args:
            value: Raw text input string.

        Returns:
            Normalized lowercase text string ready for pattern matching.
        """
        value = value.lower()

        # Unify Persian/Arabic character variants and replace zero-width spaces
        replacements = {
            "ي": "ی",
            "ى": "ی",
            "ك": "ک",
            "\u200c": " ",  # ZWNJ to space
            "\u200f": "",  # RLM
            "\u200e": "",  # LRM
        }

        for source, target in replacements.items():
            value = value.replace(source, target)

        # Remove non-spacing marks (diacritics) and formatting control characters
        value = "".join(
            character
            for character in value
            if unicodedata.category(character)
            not in {
                "Mn",
                "Cf",
            }
        )

        # Collapse repeated whitespace
        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()
