"""CLI main menu router for navigating Instagram Shop Finder tools."""

from app.cli.discovery_command import (
    run_discovery_command,
)
from app.cli.filter_command import (
    run_filter_command,
)
from app.cli.instagram_session_command import (
    run_instagram_session_command,
)
from app.cli.profile_command import (
    run_profile_command,
)
from app.cli.reprocess_command import (
    run_reprocess_command,
)


def run_menu() -> None:
    """Display the main interactive CLI menu and route the selection."""
    print()
    print("Instagram Shop Finder")
    print("=====================")

    print()
    print("1. Find shops automatically")
    print("2. Process profile manually")
    print("3. Filter saved profiles")
    print("4. Reprocess saved profiles")
    print("5. Setup Instagram session")
    print("6. Exit")

    print()

    choice = input("Select option: ").strip()

    if choice == "1":
        run_discovery_command()
        return

    if choice == "2":
        run_profile_command()
        return

    if choice == "3":
        run_filter_command()
        return

    if choice == "4":
        run_reprocess_command()
        return

    if choice == "5":
        run_instagram_session_command()
        return

    if choice == "6":
        return

    print()
    print("Invalid option.")
