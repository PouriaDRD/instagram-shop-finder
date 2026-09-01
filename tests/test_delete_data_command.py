from __future__ import annotations

from unittest.mock import (
    patch,
)

from app.cli.delete_data_command import (
    run_delete_data_command,
)


def test_delete_is_cancelled_for_y() -> None:
    with (
        patch(
            "builtins.input",
            return_value="y",
        ),
        patch("app.cli.delete_data_command." "DataResetService.reset") as reset_mock,
    ):
        run_delete_data_command()

    reset_mock.assert_not_called()


def test_delete_is_cancelled_for_yes_uppercase() -> None:
    with (
        patch(
            "builtins.input",
            return_value="YES",
        ),
        patch("app.cli.delete_data_command." "DataResetService.reset") as reset_mock,
    ):
        run_delete_data_command()

    reset_mock.assert_not_called()


def test_delete_is_cancelled_for_empty_input() -> None:
    with (
        patch(
            "builtins.input",
            return_value="",
        ),
        patch("app.cli.delete_data_command." "DataResetService.reset") as reset_mock,
    ):
        run_delete_data_command()

    reset_mock.assert_not_called()


def test_delete_runs_only_for_exact_yes() -> None:
    with (
        patch(
            "builtins.input",
            return_value="yes",
        ),
        patch("app.cli.delete_data_command." "DataResetService.reset") as reset_mock,
    ):
        reset_mock.return_value.backup_directory = "test-backup"

        reset_mock.return_value.backed_up_files = ()

        reset_mock.return_value.cleared_files = ()

        run_delete_data_command()

    reset_mock.assert_called_once()
