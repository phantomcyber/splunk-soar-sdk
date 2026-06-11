import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from typer.main import get_command

from soar_sdk.cli import cli

runner = CliRunner()
cli_command = get_command(cli.app)
PHANTOM_URL = os.environ.get("PHANTOM_URL")
PH_AUTH_TOKEN = os.environ.get("PH_AUTH_TOKEN")
PHANTOM_USERNAME = os.environ.get("PHANTOM_USERNAME")
PHANTOM_PASSWORD = os.environ.get("PHANTOM_PASSWORD")


@pytest.fixture(scope="session")
def phantom_url() -> str:
    return os.environ["PHANTOM_URL"]


@pytest.fixture(scope="session")
def ph_auth_token() -> str:
    return os.environ["PH_AUTH_TOKEN"]


@pytest.fixture(scope="session")
def phantom_credentials() -> tuple[str, str]:
    return os.environ["PHANTOM_USERNAME"], os.environ["PHANTOM_PASSWORD"]


@pytest.fixture(scope="session")
def example_app_package(tmp_path_factory, phantom_url: str) -> Path:
    package_path = tmp_path_factory.mktemp("package_install") / "example_app.tgz"
    example_app = Path(__file__).parent.parent / "example_app"

    result = runner.invoke(
        cli_command,
        [
            "package",
            "build",
            "--output-file",
            package_path.as_posix(),
            example_app.as_posix(),
        ],
    )

    assert result.exit_code == 0, result.output
    return package_path


@pytest.mark.skipif(not PHANTOM_URL, reason="PHANTOM_URL environment variable not set")
@pytest.mark.skipif(
    not PH_AUTH_TOKEN,
    reason="PH_AUTH_TOKEN environment variable not set",
)
def test_package_install_with_ph_auth_token(
    ph_auth_token: str, phantom_url: str, example_app_package: Path
):
    result = runner.invoke(
        cli_command,
        [
            "package",
            "install",
            "--force",
            example_app_package.as_posix(),
        ],
        env={
            "SOAR_INSTANCE": phantom_url,
            "PH_AUTH_TOKEN": ph_auth_token,
            "PHANTOM_USERNAME": None,
            "PHANTOM_PASSWORD": None,
        },
    )

    assert result.exit_code == 0, result.output
    assert f"App installed successfully on {phantom_url}" in result.stdout


@pytest.mark.skipif(not PHANTOM_URL, reason="PHANTOM_URL environment variable not set")
@pytest.mark.skipif(
    not PHANTOM_USERNAME or not PHANTOM_PASSWORD,
    reason="PHANTOM_USERNAME and PHANTOM_PASSWORD environment variables not set",
)
def test_package_install_with_phantom_username_password(
    phantom_credentials: tuple[str, str], phantom_url: str, example_app_package: Path
):
    username, password = phantom_credentials
    result = runner.invoke(
        cli_command,
        [
            "package",
            "install",
            "--force",
            example_app_package.as_posix(),
        ],
        env={
            "SOAR_INSTANCE": phantom_url,
            "PHANTOM_USERNAME": username,
            "PHANTOM_PASSWORD": password,
            "PH_AUTH_TOKEN": None,
        },
    )

    assert result.exit_code == 0, result.output
    assert f"App installed successfully on {phantom_url}" in result.stdout
