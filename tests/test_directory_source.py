from app.discovery.directory_source import (
    DirectoryDiscoverySource,
)


def test_extracts_direct_instagram_anchor():
    html = """
    <html>
        <body>
            <a href="https://www.instagram.com/shop_one/">
                Instagram
            </a>
        </body>
    </html>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "shop_one",
    ]


def test_extracts_username_from_text():
    html = """
    <html>
        <body>
            <p>
                اینستاگرام: beauty_shop.ir
            </p>
        </body>
    </html>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "beauty_shop.ir",
    ]


def test_extracts_username_with_at_sign():
    html = """
    <html>
        <body>
            <p>
                آدرس پیج: @toy.shop
            </p>
        </body>
    </html>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "toy.shop",
    ]


def test_deduplicates_same_username():
    html = """
    <html>
        <body>
            <a href="https://instagram.com/shop_one/">
                shop
            </a>

            <p>
                اینستاگرام: @shop_one
            </p>
        </body>
    </html>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "shop_one",
    ]


def test_ignores_instagram_navigation_paths():
    html = """
    <html>
        <body>
            <a href="https://instagram.com/explore/">
                Explore
            </a>

            <a href="https://instagram.com/reels/">
                Reels
            </a>

            <a href="https://instagram.com/real_shop/">
                Real Shop
            </a>
        </body>
    </html>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "real_shop",
    ]


def test_beauty_query_selects_beauty_seeds():
    source = DirectoryDiscoverySource()

    seeds = source._select_seed_urls("فروشگاه آرایشی")

    assert any(
        "cosmetic" in url.lower() or "mobinashop" in url.lower() for url in seeds
    )


def test_clothing_query_selects_clothing_seeds():
    source = DirectoryDiscoverySource()

    seeds = source._select_seed_urls("فروشگاه لباس زنانه")

    assert any("clothing" in url.lower() for url in seeds)


def test_custom_seeds_override_defaults():
    source = DirectoryDiscoverySource(seed_urls=("https://example.com/list",))

    seeds = source._select_seed_urls("anything")

    assert seeds == ("https://example.com/list",)


def test_rejects_numeric_false_positive():
    html = """
    <p>
        اینستاگرام: 12
    </p>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == []


def test_rejects_trailing_dot_false_positive():
    html = """
    <p>
        اینستاگرام: story.
    </p>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == []


def test_rejects_generic_instagram_words():
    html = """
    <p>
        Instagram: engagement
    </p>

    <p>
        Instagram: post
    </p>

    <p>
        Instagram: influencer
    </p>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == []


def test_extracts_explicit_at_username():
    html = """
    <p>
        فروشگاه مورد علاقه ما
        @beauty.shop_ir
    </p>
    """

    result = DirectoryDiscoverySource._extract_instagram_usernames(html)

    assert result == [
        "beauty.shop_ir",
    ]
