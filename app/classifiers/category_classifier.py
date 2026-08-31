import re
from dataclasses import dataclass

from app.models.profile import InstagramProfile, ProfileCategory


@dataclass(frozen=True, slots=True)
class CategoryClassification:
    category: ProfileCategory
    score: float
    matched_signals: tuple[str, ...]


class CategoryClassifier:
    """
    Rule-based profile category classifier.

    Important:
    Different aliases of the same concept count as ONE signal.

    Example:
        "میکاپ" + "makeup"

    represents one canonical concept and therefore contributes 0.25,
    not 0.50.
    """

    _CATEGORY_SIGNAL_GROUPS: dict[
        ProfileCategory,
        dict[str, tuple[str, ...]],
    ] = {
        ProfileCategory.BEAUTY: {
            "میکاپ": (
                "میکاپ",
                "makeup",
            ),
            "آرایشی": (
                "آرایشی",
                "ارایشی",
                "cosmetic",
                "cosmetics",
            ),
            "پوست": (
                "پوست",
                "skincare",
                "skin care",
            ),
            "مو": (
                "مو",
                "hair",
            ),
            "beauty": ("beauty",),
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
        },
        ProfileCategory.CLOTHING: {
            "لباس": (
                "لباس",
                "پوشاک",
                "clothing",
                "apparel",
            ),
            "لباس زیر": (
                "لباس زیر",
                "underwear",
                "lingerie",
            ),
            "لباس خواب": (
                "لباس خواب",
                "sleepwear",
            ),
            "مانتو": ("مانتو",),
            "شورت": ("شورت",),
            "جوراب": (
                "جوراب",
                "sock",
                "socks",
            ),
        },
        ProfileCategory.HOME: {
            "لوازم خانگی": (
                "لوازم خانگی",
                "لوازم خانه",
                "home appliance",
                "home appliances",
            ),
            "خانه": (
                "خانه",
                "home",
            ),
            "آشپزخانه": (
                "آشپزخانه",
                "اشپزخانه",
                "kitchen",
            ),
            "دکور": (
                "دکور",
                "دکوراسیون",
                "decor",
                "home decor",
            ),
        },
        ProfileCategory.ACCESSORIES: {
            "اکسسوری": (
                "اکسسوری",
                "accessory",
                "accessories",
            ),
            "گردنبند": (
                "گردنبند",
                "necklace",
            ),
            "دستبند": (
                "دستبند",
                "bracelet",
            ),
            "زیورآلات": (
                "زیورآلات",
                "زیورآلات",
                "jewelry",
                "jewellery",
            ),
            "بدلیجات": ("بدلیجات",),
            "کیف": (
                "کیف",
                "bag",
            ),
            "کفش": (
                "کفش",
                "shoe",
                "shoes",
            ),
            "عینک": (
                "عینک",
                "glasses",
                "sunglasses",
            ),
        },
        ProfileCategory.TOYS: {
            "اسباب بازی": (
                "اسباب بازی",
                "اسباب‌بازی",
                "اسباببازی",
                "اسباب بازي",
                "اسباب‌بازي",
                "اسباببازي",
                "toy",
                "toys",
                "toy store",
            ),
            "عروسک": (
                "عروسک",
                "doll",
                "dolls",
            ),
            "لگو": (
                "لگو",
                "lego",
            ),
            "بازی فکری": (
                "بازی فکری",
                "بازي فکري",
                "board game",
                "board games",
            ),
        },
    }

    _PREFIX_ALIASES: frozenset[str] = frozenset(
        {
            "شورت",
        }
    )

    _CATEGORY_PRIORITY: dict[
        ProfileCategory,
        int,
    ] = {
        ProfileCategory.TOYS: 60,
        ProfileCategory.CLOTHING: 50,
        ProfileCategory.BEAUTY: 40,
        ProfileCategory.HOME: 30,
        ProfileCategory.ACCESSORIES: 20,
        ProfileCategory.FASHION: 10,
        ProfileCategory.UNKNOWN: 0,
    }

    def classify(
        self,
        profile: InstagramProfile,
    ) -> CategoryClassification:
        text = self._normalize_text(
            " ".join(
                part
                for part in (
                    profile.display_name,
                    profile.bio,
                )
                if part
            )
        )

        matches_by_category: dict[
            ProfileCategory,
            list[str],
        ] = {}

        for (
            category,
            signal_groups,
        ) in self._CATEGORY_SIGNAL_GROUPS.items():
            matched: list[str] = []

            for canonical_signal, aliases in signal_groups.items():
                if any(
                    self._contains_signal(
                        text=text,
                        signal=self._normalize_text(alias),
                    )
                    for alias in aliases
                ):
                    matched.append(canonical_signal)

            if matched:
                matches_by_category[category] = matched

        if not matches_by_category:
            return CategoryClassification(
                category=ProfileCategory.UNKNOWN,
                score=0.0,
                matched_signals=(),
            )

        best_category = max(
            matches_by_category,
            key=lambda category: (
                len(matches_by_category[category]),
                self._CATEGORY_PRIORITY.get(
                    category,
                    0,
                ),
            ),
        )

        matched_signals = matches_by_category[best_category]

        score = min(
            1.0,
            len(matched_signals) * 0.25,
        )

        return CategoryClassification(
            category=best_category,
            score=score,
            matched_signals=tuple(matched_signals),
        )

    def _contains_signal(
        self,
        *,
        text: str,
        signal: str,
    ) -> bool:
        if signal in self._PREFIX_ALIASES:
            pattern = rf"(?<![\w])" rf"{re.escape(signal)}"
        else:
            pattern = rf"(?<![\w])" rf"{re.escape(signal)}" rf"(?![\w])"

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
