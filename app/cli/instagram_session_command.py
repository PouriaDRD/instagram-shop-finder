from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from app.config import (
    INSTAGRAM_BROWSER_PROFILE_DIR,
)


def run_instagram_session_command() -> None:
    """Open a persistent Chromium profile so the user can log in manually."""
    print()
    print("Instagram Session Setup")
    print("=======================")
    print()

    print(
        "A Chromium window will open using the app's persistent "
        "Instagram browser profile."
    )

    print(
        "Log in to Instagram manually in that window. "
        "Do not enter your password into this CLI."
    )

    print()

    INSTAGRAM_BROWSER_PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(INSTAGRAM_BROWSER_PROFILE_DIR),
            headless=False,
            locale="en-US",
            viewport={
                "width": 1440,
                "height": 1000,
            },
        )

        try:
            pages = context.pages

            page = pages[0] if pages else context.new_page()

            try:
                page.goto(
                    "https://www.instagram.com/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

            except PlaywrightTimeoutError:
                pass

            print("After Instagram is fully logged in, return here " "and press Enter.")

            input("Press Enter after login is complete: ")

            cookies = context.cookies("https://www.instagram.com/")

            cookie_names = {str(cookie.get("name", "")) for cookie in cookies}

            has_session_cookie = "sessionid" in cookie_names

            print()

            if has_session_cookie:
                print("Instagram session saved successfully.")

            else:
                print(
                    "The browser profile was saved, but an Instagram "
                    "session cookie was not detected."
                )

                print(
                    "If you were not fully logged in, run this setup "
                    "again and complete the login first."
                )

            print("Session directory: " f"{INSTAGRAM_BROWSER_PROFILE_DIR}")

        finally:
            context.close()
