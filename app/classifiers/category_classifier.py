from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import InstagramProfile, ProfileCategory


class CategoryClassificationResult(BaseModel):
    """Schema representing the outcome of categorizing an Instagram profile.

    Attributes:
        category: The assigned business or content category.
        score: Confidence score ranging from 0.0 to 1.0.
        matched_signals: Tuple of keyword signals that triggered the assigned category.
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
    """Classifies Instagram profiles into specific business domains (e.g., Beauty, Clothing, Home) based on keyword matching."""

    # Map profile categories to relevant multilingual signals (Persian/English)
    _CATEGORY_SIGNALS: dict[
        ProfileCategory,
        tuple[str, ...],
    ] = {
        ProfileCategory.BEAUTY: (
            "آرایشی",  # Cosmetics
            "میکاپ",  # Makeup
            "پوست",  # Skin
            "اسکین",  # Skin
            "skincare",
            "makeup",
            "beauty",
            "رژ",  # Lipstick
            "کرم",  # Cream
            "ریمل",  # Mascara
        ),
        ProfileCategory.FASHION: (
            "فشن",  # Fashion
            "استایل",  # Style
            "fashion",
            "style",
            "مد",  # Fashion / Trend
        ),
        ProfileCategory.CLOTHING: (
            "پوشاک",  # Apparel
            "لباس",  # Clothing
            "مانتو",  # Manto
            "شومیز",  # Blouse
            "شلوار",  # Pants
            "تیشرت",  # T-shirt
            "هودی",  # Hoodie
            "dress",
            "clothing",
        ),
        ProfileCategory.HOME: (
            "خانه",  # Home
            "هوم",  # Home
            "دکور",  # Decor
            "دکوراسیون",  # Decoration
            "آشپزخانه",  # Kitchen
            "ظروف",  # Dishes / Utensils
            "home",
            "decor",
        ),
        ProfileCategory.ACCESSORIES: (
            "اکسسوری",  # Accessories
            "زیورآلات",  # Jewelry
            "گردنبند",  # Necklace
            "دستبند",  # Bracelet
            "انگشتر",  # Ring
            "کیف",  # Bag
            "ساعت",  # Watch / Clock
            "accessory",
            "accessories",
            "jewelry",
        ),
    }

    def classify(self, profile: InstagramProfile) -> CategoryClassificationResult:
        """Analyzes an Instagram profile and identifies the primary matching domain category.

        Args:
            profile: The InstagramProfile instance to classify.

        Returns:
            A CategoryClassificationResult containing the best matching category, confidence score, and signals.
        """
        text = self._build_searchable_text(profile)

        category_matches: dict[
            ProfileCategory,
            tuple[str, ...],
        ] = {}

        # Collect matching signals for every registered category
        for category, signals in self._CATEGORY_SIGNALS.items():
            matches = self._find_matches(
                text=text,
                signals=signals,
            )

            category_matches[category] = matches

        # Identify the category with the highest signal count
        best_category = self._find_best_category(category_matches)

        best_matches = category_matches.get(
            best_category,
            (),
        )

        score = self._calculate_score(best_matches)

        # Fallback if no keywords matched across any category
        if not best_matches:
            return CategoryClassificationResult(
                category=ProfileCategory.UNKNOWN,
                score=0.0,
                matched_signals=(),
            )

        return CategoryClassificationResult(
            category=best_category,
            score=score,
            matched_signals=best_matches,
        )

    @staticmethod
    def _build_searchable_text(profile: InstagramProfile) -> str:
        """Combines display name and bio into a lowercased searchable text string.

        Args:
            profile: Profile data object.

        Returns:
            Normalized search string.
        """
        parts = (
            profile.display_name or "",
            profile.bio or "",
        )

        return " ".join(parts).lower()

    @staticmethod
    def _find_matches(*, text: str, signals: tuple[str, ...]) -> tuple[str, ...]:
        """Finds signals that exist within the searchable text string.

        Args:
            text: Lowercased searchable string.
            signals: Keywords to check.

        Returns:
            Tuple of matching keywords.
        """
        return tuple(signal for signal in signals if signal.lower() in text)

    @staticmethod
    def _find_best_category(
        category_matches: dict[
            ProfileCategory,
            tuple[str, ...],
        ],
    ) -> ProfileCategory:
        """Determines the dominant category based on the count of matched keywords.

        Args:
            category_matches: Mapping of categories to their matched signals.

        Returns:
            The ProfileCategory with the most matches.
        """
        return max(
            category_matches,
            key=lambda category: len(category_matches[category]),
        )

    @staticmethod
    def _calculate_score(matches: tuple[str, ...]) -> float:
        """Calculates a normalized score for category confidence based on match count.

        Each match adds 0.25 to the score, capped at 1.0 maximum.

        Args:
            matches: Matched signals for the selected category.

        Returns:
            A float score between 0.0 and 1.0, rounded to 2 decimal places.
        """
        if not matches:
            return 0.0

        score = len(matches) * 0.25

        return min(
            round(score, 2),
            1.0,
        )
