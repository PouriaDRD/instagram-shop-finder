from __future__ import annotations

from app.config import (
    BACKUPS_DIR,
    CANDIDATES_FILE,
    LATEST_DISCOVERY_FILE,
    LATEST_VALIDATION_FILE,
    PROFILES_FILE,
)
from app.storage.data_reset_service import (
    DataResetService,
)


def run_delete_data_command() -> None:
    print()
    print("=" * 64)
    print("DELETE STORED DATA")
    print("=" * 64)

    print()
    print("[WARNING] This operation will " "clear the application's stored data.")

    print()
    print("The following files will be cleared:")

    print("  - profiles.json")
    print("  - candidates.json")
    print("  - latest_discovery.json")
    print("  - latest_validation.json")

    print()
    print("A complete backup will be created " "before any file is changed.")

    print()
    print("Instagram browser/session data " "will NOT be deleted.")

    print()
    print("Existing backups will NOT be deleted.")

    print()
    print("To continue, type exactly:")
    print()
    print("  yes")
    print()

    confirmation = input("Confirmation: ")

    if confirmation.strip() != "yes":
        print()
        print("[CANCELLED] No data was deleted.")
        return

    service = DataResetService(
        profiles_file=(PROFILES_FILE),
        candidates_file=(CANDIDATES_FILE),
        latest_discovery_file=(LATEST_DISCOVERY_FILE),
        latest_validation_file=(LATEST_VALIDATION_FILE),
        backups_dir=(BACKUPS_DIR),
    )

    print()
    print("Creating backup...")

    try:
        result = service.reset()

    except Exception as exc:
        print()
        print("[ERROR] Data was not safely reset.")
        print(f"Reason: {exc}")
        return

    print()
    print("[BACKUP OK]")

    print("Backup directory:")

    print(f"  {result.backup_directory}")

    print()

    if result.backed_up_files:
        print("Backed up files:")

        for filename in result.backed_up_files:
            print(f"  - {filename}")

    else:
        print("No existing data files " "needed to be backed up.")

    print()
    print("[DELETE OK]")

    print("Application data has been cleared.")

    for filename in result.cleared_files:
        print(f"  - {filename}")

    print()
    print("Existing backups were preserved.")
