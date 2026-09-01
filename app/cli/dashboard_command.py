from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000
DASHBOARD_URL = f"http://{DASHBOARD_HOST}:" f"{DASHBOARD_PORT}"


def _is_dashboard_running() -> bool:
    try:
        with socket.create_connection(
            (
                DASHBOARD_HOST,
                DASHBOARD_PORT,
            ),
            timeout=0.5,
        ):
            return True

    except OSError:
        return False


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _start_dashboard_process() -> None:
    project_root = _project_root()

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.web.server",
        ],
        cwd=project_root,
        creationflags=(subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0),
    )


def _wait_until_ready(
    *,
    timeout_seconds: float = 5.0,
) -> bool:
    started_at = time.monotonic()

    while time.monotonic() - started_at < timeout_seconds:
        if _is_dashboard_running():
            return True

        time.sleep(0.15)

    return False


def run_dashboard_command() -> None:
    print()
    print("Web Dashboard")
    print("=============")
    print()

    if _is_dashboard_running():
        print("[OK] Dashboard server " "is already running.")

        print(f"Opening: {DASHBOARD_URL}")

        webbrowser.open(DASHBOARD_URL)

        return

    print("Starting dashboard server...")

    try:
        _start_dashboard_process()

    except OSError as exc:
        print()
        print("[ERROR] Could not start " "dashboard server.")
        print(f"Reason: {exc}")
        return

    if not _wait_until_ready():
        print()
        print("[ERROR] Dashboard server " "did not start correctly.")
        print("Check the dashboard server " "window for the error.")
        return

    print()
    print("[OK] Dashboard server started.")

    print(f"Opening: {DASHBOARD_URL}")

    webbrowser.open(DASHBOARD_URL)
