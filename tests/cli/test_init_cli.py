import pytest
from typer.testing import CliRunner
from soar_sdk.cli.init.cli import init


@pytest.fixture
def runner():
    return CliRunner()


def test_init_app_creates_directory_structure(runner, tmp_path):
    """Test that init command creates the expected directory structure and files."""
    app_dir = tmp_path / "test_app"

    result = runner.invoke(
        init,
        [
            "--name",
            "Test App",
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


def test_init_app_uses_provided_logos(runner, tmp_path):
    """Test that init command creates the expected directory structure and files."""
    app_dir = tmp_path / "test_app"

    logo = tmp_path / "logo.svg"
    logo_dark = tmp_path / "logo_dark.svg"
    logo.write_text("<svg>Logo</svg>")
    logo_dark.write_text("<svg>Dark Logo</svg>")

    result = runner.invoke(
        init,
        [
            "--name",
            "Test App",
            "--description",
            "A test app",
            "--app-dir",
            str(app_dir),
            "--logo",
            str(logo),
            "--logo-dark",
            str(logo_dark),
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

    assert (app_dir / "logo.svg").read_text() == "<svg>Logo</svg>"
    assert (app_dir / "logo_dark.svg").read_text() == "<svg>Dark Logo</svg>"


def test_init_app_fails_on_non_empty_directory_without_overwrite(runner, tmp_path):
    """Test that init command fails when target directory is not empty and overwrite is not specified."""
    app_dir = tmp_path / "existing_app"
    app_dir.mkdir()
    (app_dir / "existing_file.txt").touch()

    result = runner.invoke(
        init,
        [
            "--name",
            "Test App",
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

    result = runner.invoke(
        init,
        [
            "--name",
            "Test App",
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
