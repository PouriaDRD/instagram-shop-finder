from __future__ import annotations

from unittest.mock import patch

from app.cli.dashboard_command import (
    DASHBOARD_URL,
    run_dashboard_command,
)


def test_existing_dashboard_is_opened_without_new_process() -> None:
    with (
        patch(
            "app.cli.dashboard_command." "_is_dashboard_running",
            return_value=True,
        ),
        patch(
            "app.cli.dashboard_command." "_start_dashboard_process",
        ) as start_mock,
        patch(
            "app.cli.dashboard_command." "webbrowser.open",
        ) as browser_mock,
    ):
        run_dashboard_command()

    start_mock.assert_not_called()

    browser_mock.assert_called_once_with(DASHBOARD_URL)


def test_dashboard_process_starts_when_not_running() -> None:
    with (
        patch(
            "app.cli.dashboard_command." "_is_dashboard_running",
            return_value=False,
        ),
        patch(
            "app.cli.dashboard_command." "_start_dashboard_process",
        ) as start_mock,
        patch(
            "app.cli.dashboard_command." "_wait_until_ready",
            return_value=True,
        ),
        patch(
            "app.cli.dashboard_command." "webbrowser.open",
        ) as browser_mock,
    ):
        run_dashboard_command()

    start_mock.assert_called_once()

    browser_mock.assert_called_once_with(DASHBOARD_URL)


def test_browser_is_not_opened_when_server_fails_to_start() -> None:
    with (
        patch(
            "app.cli.dashboard_command." "_is_dashboard_running",
            return_value=False,
        ),
        patch(
            "app.cli.dashboard_command." "_start_dashboard_process",
        ),
        patch(
            "app.cli.dashboard_command." "_wait_until_ready",
            return_value=False,
        ),
        patch(
            "app.cli.dashboard_command." "webbrowser.open",
        ) as browser_mock,
    ):
        run_dashboard_command()

    browser_mock.assert_not_called()


def test_start_error_does_not_open_browser() -> None:
    with (
        patch(
            "app.cli.dashboard_command." "_is_dashboard_running",
            return_value=False,
        ),
        patch(
            "app.cli.dashboard_command." "_start_dashboard_process",
            side_effect=OSError("test failure"),
        ),
        patch(
            "app.cli.dashboard_command." "webbrowser.open",
        ) as browser_mock,
    ):
        run_dashboard_command()

    browser_mock.assert_not_called()
