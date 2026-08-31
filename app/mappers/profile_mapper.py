from app.models.profile import InstagramProfile
from app.models.raw_profile import RawProfileData


class ProfileMapper:

    @staticmethod
    def from_raw(raw: RawProfileData) -> InstagramProfile:

        return InstagramProfile(
            username=raw.username,
            profile_url=("https://www.instagram.com/" f"{raw.username}/"),
            display_name=raw.display_name,
            bio=raw.bio,
            external_links=raw.external_links,
            followers_count=raw.followers_count,
            following_count=raw.following_count,
            posts_count=raw.posts_count,
            is_public=raw.is_public,
        )
