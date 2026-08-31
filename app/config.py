from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

PROFILES_FILE = DATA_DIR / "profiles.json"

INSTAGRAM_BROWSER_PROFILE_DIR = DATA_DIR / "instagram-browser-profile"
