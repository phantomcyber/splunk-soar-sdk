from unittest import mock

import typer
from typer.testing import CliRunner

import soar_sdk.cli.cli as cli_module
from soar_sdk.cli.cli import app, main


# Create a test runner
runner = CliRunner()


def test_cli_app_initialization():
    """Test that the Typer app is initialized correctly with the right settings."""
    assert isinstance(app, typer.Typer)
    assert app.info.help == "A command-line tool for helping with SOAR Apps development"
    assert app.info.context_settings == {"help_option_names": ["-h", "--help"]}


def test_cli_app_adds_manifests_subcommand():
    """Test that the manifests subcommand is added to the app."""
    with mock.patch.object(typer.Typer, "add_typer") as mock_add_typer:
        # Re-import to trigger the add_typer call
        import importlib

        importlib.reload(cli_module)

        # Check that add_typer was called with the manifests module and the right name
        mock_add_typer.assert_called_once()
        args, kwargs = mock_add_typer.call_args
        assert kwargs.get("name") == "manifests"


def test_main_function_calls_app():
    """Test that the main function calls the app instance."""
    # Mock the app to avoid it actually trying to run
    with mock.patch.object(cli_module, "app") as mock_app:
        main()
        mock_app.assert_called_once()


def test_main_execution_on_name_main():
    """Test the __name__ == "__main__" block exists and would execute main()."""
    # Directly inspect the source code to verify the main check exists
    with open(cli_module.__file__, "r") as f:
        source_code = f.read()

    # Verify the module contains the if __name__ == "__main__" check
    assert 'if __name__ == "__main__":' in source_code

    # Now manually test the behavior by simulating the condition
    with mock.patch.object(cli_module, "main") as mock_main:
        # Execute just the if block from the module with our mock
        if_main_block = """
if __name__ == "__main__":
    main()
"""
        # Set __name__ to __main__ for the sake of this test
        module_globals = {"__name__": "__main__", "main": mock_main}
        exec(if_main_block, module_globals)

        # Verify main() was called
        mock_main.assert_called_once()


def test_cli_help_option():
    """Test the CLI shows help information when --help is passed."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "A command-line tool for helping with SOAR Apps development" in result.stdout
    assert "manifests" in result.stdout


def test_cli_manifests_subcommand():
    """Test the manifests subcommand is available and shows help."""
    result = runner.invoke(app, ["manifests", "--help"])
    assert result.exit_code == 0
    assert "display" in result.stdout
    assert "create" in result.stdout


def test_cli_manifests_commands_help():
    """Test that the manifests subcommands show help information."""
    # Test display command
    result = runner.invoke(app, ["manifests", "display", "--help"])
    assert result.exit_code == 0
    assert "FILENAME" in result.stdout

    # Test create command
    result = runner.invoke(app, ["manifests", "create", "--help"])
    assert result.exit_code == 0
    assert "FILENAME" in result.stdout
    assert "PROJECT_CONTEXT" in result.stdout
