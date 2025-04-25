from unittest import mock

import typer
from typer.testing import CliRunner

from soar_sdk.cli import cli


# Create a test runner
runner = CliRunner()


def test_cli_app_initialization():
    """Test that the Typer app is initialized correctly with the right settings."""
    assert isinstance(cli.app, typer.Typer)
    assert cli.app.info.help == cli.HELP
    assert cli.app.info.context_settings == cli.CONTEXT_SETTINGS


def test_main_function_calls_app():
    """Test that the main function calls the app instance."""
    # Mock the app to avoid it actually trying to run
    with mock.patch.object(cli, "app") as mock_app:
        cli.main()
        mock_app.assert_called_once()


def test_cli_manifests_subcommand():
    """Test the manifests subcommand is available and shows help."""
    result = runner.invoke(cli.app, ["manifests", "--help"])
    assert result.exit_code == 0
    assert "display" in result.stdout
    assert "create" in result.stdout


def test_cli_manifests_commands_help():
    """Test that the manifests subcommands show help information."""
    # Test display command
    result = runner.invoke(cli.app, ["manifests", "display", "--help"])
    assert result.exit_code == 0
    assert "FILENAME" in result.stdout

    # Test create command
    result = runner.invoke(cli.app, ["manifests", "create", "--help"])
    assert result.exit_code == 0
    assert "FILENAME" in result.stdout
    assert "PROJECT_CONTEXT" in result.stdout


def test_install_command_help():
    # Run the `install` command with the `--help` flag
    result = runner.invoke(cli.app, ["package", "install", "--help"])

    # Assert the command executed successfully
    assert result.exit_code == 0

    # Assert that the help text contains the expected arguments and options
    assert "app_tarball" in result.output
    assert "soar_instance" in result.output
