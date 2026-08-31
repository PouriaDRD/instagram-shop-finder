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
    print()
    print("Instagram Shop Finder")
    print("=====================")

    print()
    print("1. Process profile")
    print("2. Filter saved profiles")
    print("3. Reprocess saved profiles")
    print("4. Exit")

    print()

    choice = input("Select option: ").strip()

    if choice == "1":
        run_profile_command()
        return

    if choice == "2":
        run_filter_command()
        return

    if choice == "3":
        run_reprocess_command()
        return

    if choice == "4":
        return

    print()
    print("Invalid option.")
