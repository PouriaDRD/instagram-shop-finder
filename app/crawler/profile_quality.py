from __future__ import annotations

from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)
from app.models.profile_quality import (
    ProfileDataQuality,
    ProfileDataQualityStatus,
)
from app.models.raw_profile import (
    RawProfileData,
)


class ProfileQualityEvaluator:
    """Detect suspiciously incomplete Instagram profile reads.

    The evaluator intentionally does not decide whether the account
    is a shop.

    Its only responsibility is identifying data that should not be
    trusted enough for a permanent REJECT decision.
    """

    def evaluate(
        self,
        *,
        raw: RawProfileData,
        profile: InstagramProfile,
        expected_category: ProfileCategory | None,
        min_shop_score: float,
    ) -> ProfileDataQuality:
        reasons: list[str] = []

        display_name = (raw.display_name or "").strip()

        bio = (raw.bio or "").strip()

        has_links = bool(raw.external_links)

        followers = raw.followers_count

        following = raw.following_count

        posts = raw.posts_count

        metrics_all_zero = followers == 0 and following == 0 and posts == 0

        # A search-discovered public account that returns zero for
        # every metric is suspicious regardless of whether some
        # header text was visible.
        if metrics_all_zero:
            reasons.append("all Instagram profile metrics " "were returned as zero")

        if followers > 0 and not display_name and not bio:
            reasons.append(
                "followers were available but " "display name and bio were missing"
            )

        score = profile.shop_score if profile.shop_score is not None else 0.0

        # Strong indication that the profile page was only partially
        # parsed: followers exist, expected category was detected,
        # but there is almost no textual/commercial material.
        if (
            followers > 0
            and expected_category is not None
            and profile.category == expected_category
            and score < min_shop_score
            and not has_links
            and len(display_name + bio) < 12
        ):
            reasons.append(
                "target category and followers "
                "were available but profile content "
                "was unusually sparse"
            )

        # Another suspicious combination:
        # a substantial profile but completely empty content.
        if (
            followers >= 10_000
            and posts > 0
            and not bio
            and not display_name
            and not has_links
        ):
            reasons.append(
                "substantial profile metrics were "
                "available but all profile content "
                "was missing"
            )

        if reasons:
            return ProfileDataQuality(
                status=(ProfileDataQualityStatus.INCOMPLETE),
                reasons=reasons,
            )

        return ProfileDataQuality(
            status=(ProfileDataQualityStatus.COMPLETE),
        )
