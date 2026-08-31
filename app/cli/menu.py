"""CLI main menu router for navigating Instagram Shop Finder tools."""

from app.cli.discovery_command import (
    run_discovery_command,
)
from app.cli.filter_command import (
    run_filter_command,
)
from app.cli.profile_command import (
    run_profile_command,
)
from app.cli.reprocess_command import (
    run_reprocess_command,
)


def run_menu() -> None:
    """Displays the main interactive CLI menu and routes user selection to commands.

    Presents options for automated shop discovery, manual profile processing, stored profile
    filtering, and batch reprocessing. Evaluates user selection and delegates execution
    to the corresponding sub-command handler function.
    """
    print()
    print("Instagram Shop Finder")
    print("=====================")

    print()
    print("1. Find shops automatically")
    print("2. Process profile manually")
    print("3. Filter saved profiles")
    print("4. Reprocess saved profiles")
    print("5. Exit")

    print()

    choice = input("Select option: ").strip()

    # Route Option 1: Automated web search discovery engine
    if choice == "1":
        run_discovery_command()
        return

    # Route Option 2: Single Instagram profile manual scraping & classification
    if choice == "2":
        run_profile_command()
        return

    # Route Option 3: Filter local JSON storage by follower counts, categories, and scores
    if choice == "3":
        run_filter_command()
        return

    # Route Option 4: Re-evaluate stored profiles with updated classifiers
    if choice == "4":
        run_reprocess_command()
        return

    # Route Option 5: Exit application loop gracefully
    if choice == "5":
        return

    # Catch-all fallback for unrecognized numeric or character input
    print()
    print("Invalid option.")
