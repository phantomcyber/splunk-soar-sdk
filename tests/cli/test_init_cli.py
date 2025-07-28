import json
import textwrap
from uuid import uuid4
import pytest
from typer.testing import CliRunner
from soar_sdk.cli.init.cli import init, resolve_dependencies, get_app_json
from unittest.mock import patch


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
    assert (app_dir / "logo.svg").exists()
    assert (app_dir / "logo_dark.svg").exists()


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
