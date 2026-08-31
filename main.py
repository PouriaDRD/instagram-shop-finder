from app.config import PROFILES_FILE
from app.models.profile import InstagramProfile, ProfileCategory
from app.storage.json_storage import JsonProfileStorage


def main() -> None:

    storage = JsonProfileStorage(
        PROFILES_FILE,
    )

    profile = InstagramProfile(
        username="sample_beauty_shop",
        display_name="Sample Beauty Shop",
        bio="فروش لوازم آرایشی و ارسال سراسر کشور",
        followers_count=5200,
        following_count=810,
        posts_count=240,
        is_public=True,
        category=ProfileCategory.BEAUTY,
        is_shop=True,
    )

    storage.save(profile)

    profiles = storage.get_all()

    for item in profiles:
        print(
            item.username,
            item.followers_count,
            item.category,
        )


if __name__ == "__main__":
    main()
