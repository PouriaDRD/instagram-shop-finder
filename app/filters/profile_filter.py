from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.profile import InstagramProfile, ProfileCategory


class ProfileFilter(BaseModel):
    """Schema representing filtering criteria for Instagram profiles.

    Attributes:
        is_shop: Filter by shop status (True for shops, False for non-shops).
        category: Filter by specific business or content category.
        min_followers: Minimum follower count threshold (inclusive).
        max_followers: Maximum follower count threshold (inclusive).
        min_shop_score: Minimum shop confidence score threshold (0.0 to 1.0).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    is_shop: bool | None = None

    category: ProfileCategory | None = None

    min_followers: int | None = Field(
        default=None,
        ge=0,
    )

    max_followers: int | None = Field(
        default=None,
        ge=0,
    )

    min_shop_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_follower_range(self) -> "ProfileFilter":
        """Ensures that min_followers does not exceed max_followers when both are provided.

        Returns:
            The validated ProfileFilter instance.

        Raises:
            ValueError: If min_followers is strictly greater than max_followers.
        """
        if (
            self.min_followers is not None
            and self.max_followers is not None
            and self.min_followers > self.max_followers
        ):
            raise ValueError("min_followers cannot be greater than max_followers.")

        return self


class ProfileFilterEngine:
    """Engine responsible for matching and filtering collections of Instagram profiles against given criteria."""

    def filter(
        self,
        profiles: list[InstagramProfile],
        criteria: ProfileFilter,
    ) -> list[InstagramProfile]:
        """Filters a list of Instagram profiles according to specified criteria.

        Args:
            profiles: List of InstagramProfile objects to evaluate.
            criteria: ProfileFilter instance containing matching conditions.

        Returns:
            A new list containing only profiles that meet all criteria.
        """
        return [
            profile
            for profile in profiles
            if self.matches(
                profile=profile,
                criteria=criteria,
            )
        ]

    def matches(self, *, profile: InstagramProfile, criteria: ProfileFilter) -> bool:
        """Checks whether a single Instagram profile satisfies all active filter conditions.

        Args:
            profile: The InstagramProfile instance to evaluate.
            criteria: Filtering criteria to test against.

        Returns:
            True if the profile matches all specified criteria, False otherwise.
        """
        # Validate shop flag matching
        if criteria.is_shop is not None and profile.is_shop != criteria.is_shop:
            return False

        # Validate domain category matching
        if criteria.category is not None and profile.category != criteria.category:
            return False

        # Validate lower bound on follower count
        if (
            criteria.min_followers is not None
            and profile.followers_count < criteria.min_followers
        ):
            return False

        # Validate upper bound on follower count
        if (
            criteria.max_followers is not None
            and profile.followers_count > criteria.max_followers
        ):
            return False

        # Validate minimum shop score (requires a non-None score on the profile)
        if criteria.min_shop_score is not None:
            if profile.shop_score is None:
                return False

            if profile.shop_score < criteria.min_shop_score:
                return False

        return True
