import json
import textwrap
from unittest.mock import patch
from uuid import uuid4

import click
import pytest
from rich.console import Console
from typer.testing import CliRunner

from soar_sdk.cli.init import cli as init_cli
from soar_sdk.cli.init import wizard
from soar_sdk.cli.init.cli import get_app_json, init, resolve_dependencies
from soar_sdk.compat import PythonVersion


@pytest.fixture
def runner():
    return CliRunner()


def test_init_app_creates_directory_structure(runner, tmp_path):
    """Test that init command creates the expected directory structure and files."""
    app_dir = tmp_path / "test_app"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
            ],
        )

    assert result.exit_code == 0
    assert app_dir.exists()
    assert (app_dir / "src").is_dir()
    assert (app_dir / "src" / "__init__.py").exists()
    assert (app_dir / "src" / "app.py").exists()
    assert (app_dir / "pyproject.toml").exists()
    assert (app_dir / ".pre-commit-config.yaml").exists()
    assert (app_dir / "logo.svg").exists()
    assert (app_dir / "logo_dark.svg").exists()


def test_init_app_defaults_app_dir_to_app_name(runner):
    """Test that one-shot init defaults app dir to pwd/app_name."""
    with patch("soar_sdk.cli.init.cli.init_sdk_app") as mock_init_sdk_app:
        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
            ],
        )

    assert result.exit_code == 0
    mock_init_sdk_app.assert_called_once()
    assert mock_init_sdk_app.call_args.args[6] == init_cli.WORK_DIR / "test_app"


def test_init_app_non_interactive_flag_allows_one_shot_usage(runner):
    """Test that --non-interactive still allows complete one-shot init usage."""
    with patch("soar_sdk.cli.init.cli.init_sdk_app") as mock_init_sdk_app:
        result = runner.invoke(
            init,
            [
                "--non-interactive",
                "--name",
                "test_app",
                "--description",
                "A test app",
            ],
        )

    assert result.exit_code == 0
    mock_init_sdk_app.assert_called_once()


def test_init_app_includes_static_tests_by_default(runner, tmp_path):
    """Test that init command generates public pre-commit config by default."""
    app_dir = tmp_path / "test_app"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
            ],
        )

    assert result.exit_code == 0
    pre_commit_config = (app_dir / ".pre-commit-config.yaml").read_text()
    assert "- id: static-tests" in pre_commit_config


def test_init_app_public_flag_includes_static_tests(runner, tmp_path):
    """Test that --public explicitly generates Splunkbase static tests."""
    app_dir = tmp_path / "test_app"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
                "--public",
            ],
        )

    assert result.exit_code == 0
    pre_commit_config = (app_dir / ".pre-commit-config.yaml").read_text()
    assert "- id: static-tests" in pre_commit_config


def test_init_app_private_flag_omits_static_tests(runner, tmp_path):
    """Test that --private omits Splunkbase-only static tests."""
    app_dir = tmp_path / "test_app"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
                "--private",
            ],
        )

    assert result.exit_code == 0
    pre_commit_config = (app_dir / ".pre-commit-config.yaml").read_text()
    assert "repo: https://github.com/phantomcyber/dev-cicd-tools" in pre_commit_config
    assert "- id: release-notes" in pre_commit_config
    assert "- id: static-tests" not in pre_commit_config


def test_init_with_partial_args_fails_without_prompting(runner):
    """Test that partial one-shot init usage fails instead of prompting."""
    result = runner.invoke(init, ["--name", "test_app"])
    output = click.unstyle(result.output)

    assert result.exit_code != 0
    assert "Invalid value for --description" in output
    assert "the guided wizard with no options" in output
    assert "App description" not in output


def test_init_without_args_in_non_tty_prints_required_options(runner):
    """Test that no-arg init does not run the wizard outside a TTY."""
    with (
        patch("soar_sdk.cli.init.cli._is_tty", return_value=False),
        patch("soar_sdk.cli.init.cli.run_init_wizard") as mock_run_init_wizard,
    ):
        result = runner.invoke(init, [])

    output = click.unstyle(result.output)
    assert result.exit_code == 1
    assert "Interactive app initialization is unavailable" in output
    assert "soarapps init --name <app_name> --description <description>" in output
    assert "--name" in output
    assert "--description" in output
    mock_run_init_wizard.assert_not_called()


def test_init_non_interactive_flag_without_args_prints_required_options(runner):
    """Test that --non-interactive disables the no-arg wizard."""
    with (
        patch("soar_sdk.cli.init.cli._is_tty", return_value=True),
        patch("soar_sdk.cli.init.cli.run_init_wizard") as mock_run_init_wizard,
    ):
        result = runner.invoke(init, ["--non-interactive"])

    output = click.unstyle(result.output)
    assert result.exit_code == 1
    assert "Interactive app initialization is unavailable" in output
    assert "soarapps init --name <app_name> --description <description>" in output
    assert "--name" in output
    assert "--description" in output
    mock_run_init_wizard.assert_not_called()


def test_init_tty_detection_requires_stdin_and_stdout():
    """Test that init wizard TTY detection requires stdin and stdout."""
    with (
        patch("soar_sdk.cli.init.cli.sys.stdin") as stdin,
        patch("soar_sdk.cli.init.cli.sys.stdout") as stdout,
    ):
        stdin.isatty.return_value = True
        stdout.isatty.return_value = True
        assert init_cli._is_tty() is True

        stdout.isatty.return_value = False
        assert init_cli._is_tty() is False

        stdin.isatty.return_value = False
        assert init_cli._is_tty() is False


def test_init_wizard_creates_public_app(runner, tmp_path):
    """Test that no-arg init runs the guided wizard and creates a public app."""
    app_dir = tmp_path / "test_app"
    wizard_input = "\n".join(
        [
            "test_app",
            "A test app",
            str(app_dir),
            "y",
            "n",
            "y",
        ]
    )

    with (
        patch("soar_sdk.cli.init.cli._is_tty", return_value=True),
        patch("subprocess.run"),
        patch("shutil.which") as mock_which,
    ):
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(init, [], input=f"{wizard_input}\n")

    assert result.exit_code == 0
    assert app_dir.exists()
    assert (app_dir / "src" / "app.py").exists()
    pre_commit_config = (app_dir / ".pre-commit-config.yaml").read_text()
    assert "- id: static-tests" in pre_commit_config


def test_init_wizard_creates_private_app(runner, tmp_path):
    """Test that the guided wizard can create a private app."""
    app_dir = tmp_path / "test_app"
    wizard_input = "\n".join(
        [
            "test_app",
            "A test app",
            str(app_dir),
            "n",
            "n",
            "y",
        ]
    )

    with (
        patch("soar_sdk.cli.init.cli._is_tty", return_value=True),
        patch("subprocess.run"),
        patch("shutil.which") as mock_which,
    ):
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(init, [], input=f"{wizard_input}\n")

    assert result.exit_code == 0
    pre_commit_config = (app_dir / ".pre-commit-config.yaml").read_text()
    assert "- id: release-notes" in pre_commit_config
    assert "- id: static-tests" not in pre_commit_config


def test_init_wizard_defaults_app_dir_to_app_name_under_working_dir(tmp_path):
    """Test that the guided wizard defaults app dir to pwd/app_name."""
    console = Console(record=True)

    with (
        patch(
            "soar_sdk.cli.init.wizard.Prompt.ask",
            side_effect=[
                "test_app",
                "A test app",
                str(tmp_path / "test_app"),
            ],
        ) as ask_mock,
        patch(
            "soar_sdk.cli.init.wizard.Confirm.ask",
            side_effect=[True, False, True],
        ),
    ):
        config = wizard.run_init_wizard(console=console, default_app_dir=tmp_path)

    assert config is not None
    assert config.app_dir == tmp_path / "test_app"
    ask_mock.assert_any_call("App directory", default=str(tmp_path / "test_app"))


def test_init_wizard_cancel_does_not_create_app(runner, tmp_path):
    """Test that cancelling the guided wizard exits before creating files."""
    app_dir = tmp_path / "test_app"
    wizard_input = "\n".join(
        [
            "test_app",
            "A test app",
            str(app_dir),
            "y",
            "n",
            "n",
        ]
    )

    with patch("soar_sdk.cli.init.cli._is_tty", return_value=True):
        result = runner.invoke(init, [], input=f"{wizard_input}\n")

    assert result.exit_code == 0
    assert "App creation cancelled" in result.output
    assert not app_dir.exists()


def test_init_wizard_advanced_settings(runner, tmp_path):
    """Test that the guided wizard applies advanced settings."""
    app_dir = tmp_path / "advanced_app"
    wizard_input = "\n".join(
        [
            "advanced_app",
            "An advanced app",
            str(app_dir),
            "y",
            "y",
            "Alice Example,Bob Example",
            "3.13",
            "requests>=2.0,httpx",
            "2.3.4",
            "endpoint",
            "Acme",
            "Acme Apps",
            "Acme Product",
            "y",
            "https://packages.example/simple",
            "n",
            "y",
        ]
    )

    with (
        patch("soar_sdk.cli.init.cli._is_tty", return_value=True),
        patch("subprocess.run"),
        patch("shutil.which") as mock_which,
    ):
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(init, [], input=f"{wizard_input}\n")

    assert result.exit_code == 0
    pyproject = (app_dir / "pyproject.toml").read_text()
    assert 'version = "2.3.4"' in pyproject
    assert 'requires-python = ">=3.13, <3.14"' in pyproject
    assert '{ name = "Alice Example" }' in pyproject
    assert '{ name = "Bob Example" }' in pyproject
    assert '"requests>=2.0"' in pyproject
    assert '"httpx"' in pyproject
    assert 'url = "https://packages.example/simple"' in pyproject

    app_py = (app_dir / "src" / "app.py").read_text()
    assert "app_type='endpoint'" in app_py
    assert "product_vendor='Acme'" in app_py
    assert "product_name='Acme Product'" in app_py
    assert "publisher='Acme Apps'" in app_py
    assert "fips_compliant=True" in app_py


def test_init_wizard_required_prompt_retries_on_empty_value():
    """Test that required wizard prompts reject empty input."""
    console = Console(record=True)

    with patch("soar_sdk.cli.init.wizard.Prompt.ask", side_effect=["", "test_app"]):
        value = wizard._ask_required("App name", console=console)

    assert value == "test_app"
    assert "App name is required" in console.export_text()


def test_init_wizard_csv_prompt_returns_empty_list_for_empty_value():
    """Test that optional CSV wizard prompts accept empty input."""
    with patch("soar_sdk.cli.init.wizard.Prompt.ask", return_value=""):
        value = wizard._ask_csv("Authors")

    assert value == []


def test_init_wizard_python_versions_prompt_retries_on_invalid_value():
    """Test that Python version wizard prompts retry invalid input."""
    console = Console(record=True)

    with patch("soar_sdk.cli.init.wizard.Prompt.ask", side_effect=["3.12", "3.13"]):
        value = wizard._ask_python_versions(console)

    assert value == [PythonVersion.PY_3_13]
    assert "Unsupported Python version: 3.12" in console.export_text()


def test_init_app_fails_on_non_empty_directory_without_overwrite(runner, tmp_path):
    """Test that init command fails when target directory is not empty and overwrite is not specified."""
    app_dir = tmp_path / "existing_app"
    app_dir.mkdir()
    (app_dir / "existing_file.txt").touch()

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
            ],
        )

    assert result.exit_code == 1
    assert "not empty" in result.stdout


def test_init_app_overwrites_existing_directory_with_overwrite_flag(runner, tmp_path):
    """Test that init command overwrites existing directory when --overwrite flag is used."""
    app_dir = tmp_path / "existing_app"
    app_dir.mkdir()
    existing_file = app_dir / "existing_file.txt"
    existing_file.write_text("existing content")

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
                "--overwrite",
            ],
        )

    assert result.exit_code == 0
    assert app_dir.exists()
    assert not existing_file.exists()
    assert (app_dir / "src" / "app.py").exists()
    assert (app_dir / "pyproject.toml").exists()


def test_init_without_git_installed_fails(runner, tmp_path):
    """Test that init command fails if git is not installed."""
    app_dir = tmp_path / "test_app"

    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: None if x == "git" else "/usr/bin/example"
        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
            ],
        )

    assert result.exit_code != 0
    assert "git command not found" in result.stdout


def test_init_without_uv_installed_fails(runner, tmp_path):
    """Test that init command fails if uv is not installed."""
    app_dir = tmp_path / "test_app"

    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: None if x == "uv" else "/usr/bin/example"
        result = runner.invoke(
            init,
            [
                "--name",
                "test_app",
                "--description",
                "A test app",
                "--app-dir",
                str(app_dir),
            ],
        )

    assert result.exit_code != 0
    assert "uv command not found" in result.stdout


def test_resolve_dependencies(tmp_path):
    """Test that resolve_dependencies processes requirements.txt and calls uv add correctly."""

    # Setup test directories
    app_dir = tmp_path / "app"
    output_dir = tmp_path / "output"
    app_dir.mkdir()
    output_dir.mkdir()

    # Create requirements.txt with various dependency formats
    (app_dir / "requirements.txt").write_text(
        textwrap.dedent(
            """
            requests>=2.25.0
            beautifulsoup4==4.9.3
            # This is a comment
            urllib3~=1.26.0
            httpx[http2]==0.27.2

            invalid-dep-with-@-symbol@
            numpy
            """
        )
    )

    with patch("soar_sdk.cli.init.cli.subprocess.run") as mock_run:
        resolve_dependencies(app_dir, output_dir)

        # Verify subprocess.run was called with correct arguments
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

    # Check the command arguments
    cmd_arg = args[0]
    expected_deps = {
        "splunk-soar-sdk",
        "requests>=2.25.0",
        "beautifulsoup4==4.9.3",
        "urllib3~=1.26.0",
        "httpx[http2]==0.27.2",
        "numpy",
    }

    assert cmd_arg[:2] == ["uv", "add"]
    assert set(cmd_arg[2:]) == expected_deps
    assert kwargs["cwd"] == output_dir
    assert kwargs["check"] is True


def test_resolve_dependencies_no_requirements(tmp_path):
    """Test that resolve_dependencies does nothing when no requirements.txt exists."""

    app_dir = tmp_path / "app"
    output_dir = tmp_path / "output"
    app_dir.mkdir()
    output_dir.mkdir()

    with patch("soar_sdk.cli.init.cli.subprocess.run") as mock_run:
        resolve_dependencies(app_dir, output_dir)

        # Verify subprocess.run was called with correct arguments
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

    # Check the command arguments
    cmd_arg = args[0]
    assert cmd_arg == ["uv", "add", "splunk-soar-sdk"]
    assert kwargs["cwd"] == output_dir
    assert kwargs["check"] is True


def test_get_app_json(tmp_path):
    """Test that get_app_json finds and returns the correct app JSON file."""

    # Create a valid app JSON file
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    valid_json = app_dir / "valid_app.json"
    valid_json.write_text('{"main_module": "app.py", "name": "Test App"}')

    # Create an invalid JSON file (not an app manifest)
    invalid_json = app_dir / "invalid.json"
    invalid_json.write_text('{"some_field": "value"}')

    # Create a postman collection (should be skipped)
    postman_json = app_dir / "test.postman_collection.json"
    postman_json.write_text('{"info": {"name": "Postman Collection"}}')

    result = get_app_json(app_dir)
    assert result == valid_json


def test_get_app_json_multiple_valid_files(tmp_path):
    """Test that get_app_json returns one of the valid app JSON files when multiple exist."""

    app_dir = tmp_path / "app"
    app_dir.mkdir()

    # Create multiple valid app JSON files
    app1_json = app_dir / "app1.json"
    app1_json.write_text('{"main_module": "app1.py", "name": "App 1"}')

    app2_json = app_dir / "app2.json"
    app2_json.write_text('{"main_module": "app2.py", "name": "App 2"}')

    result = get_app_json(app_dir)
    # Should return one of the valid files
    assert result in [app1_json, app2_json]


def test_get_app_json_no_valid_files(tmp_path):
    """Test that get_app_json raises FileNotFoundError when no valid app JSON exists."""

    app_dir = tmp_path / "app"
    app_dir.mkdir()

    # Create only invalid files
    (app_dir / "not_a_manifest.json").write_text(json.dumps({"some_field": "value"}))
    (app_dir / "test.postman_collection.json").write_text(
        json.dumps({"main_module": "skip_this"})
    )
    (app_dir / "malformed.json").write_text('{"invalid": json}')

    with pytest.raises(FileNotFoundError, match="No valid app manifest found"):
        get_app_json(app_dir)


def test_get_app_json_valid(tmp_path):
    """Test that get_app_json returns the valid app JSON file when one exists."""

    app_dir = tmp_path / "app"
    app_dir.mkdir()

    # Create valid JSON file with random name
    valid_json = app_dir / f"{uuid4()}.json"
    valid_json.write_text(json.dumps({"main_module": "app.py"}))

    result = get_app_json(app_dir)
    assert result == valid_json


def test_get_app_json_empty_directory(tmp_path):
    """Test that get_app_json raises FileNotFoundError in empty directory."""

    app_dir = tmp_path / "empty_app"
    app_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="No valid app manifest found"):
        get_app_json(app_dir)
