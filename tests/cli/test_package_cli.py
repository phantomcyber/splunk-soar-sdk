import tarfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import httpx
import pytest
import respx
import toml
from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package
from soar_sdk.cli.package.utils import phantom_get_login_session, phantom_install_app
from soar_sdk.cli.path_utils import context_directory
from soar_sdk.meta.dependencies import UvWheel

runner = CliRunner()


def test_package_build_command(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    # Create the patch for hash validation
    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert destination.is_file()
    # Verify our mock was called
    assert wheel_resp_mock.called


def test_package_build_command_specifying_outdir(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    fake_wheel = tmp_path / "fake.whl"
    with fake_wheel.open("wb") as whl:
        whl.write(b"deadbeef")

    # Create the patch for hash validation
    with patch.object(UvWheel, "validate_hash", return_value=None):
        result = runner.invoke(
            package,
            [
                "build",
                "--output-file",
                destination.as_posix(),
                example_app.as_posix(),
                "--with-sdk-wheel-from",
                fake_wheel.as_posix(),
            ],
        )

    assert result.exit_code == 0
    assert destination.is_file()
    # Verify our mock was called
    assert wheel_resp_mock.called


def set_up_install_request_responses(mocked_session):
    """
    Setting up the expected responses for the mocked session that the install command expects.
    """
    mock_get = mocked_session.get
    mock_get.return_value.cookies.get_dict.return_value = {
        "csrftoken": "mocked_csrf_token"
    }

    mock_post = mocked_session.post
    mock_post.return_value.cookies.get_dict.return_value = {
        "csrftoken": "mocked_csrf_token",
        "sessionid": "mocked_session_id",
    }
    return mock_get, mock_post


def test_install_command(mock_install_client, app_tarball: Path):
    result = runner.invoke(
        package,
        [
            "install",
            app_tarball.as_posix(),
            "10.1.23.4",
            "--username",
            "admin",
        ],
        input="test_password",
    )

    assert result.exit_code == 0

    assert mock_install_client.get("/").called
    assert mock_install_client.post("app_install").called

    app_install_call = mock_install_client.post("app_install")
    assert app_install_call.call_count == 1
    expected_csrf_header = "fake_csrf_token"
    assert (
        app_install_call.calls[0].request.headers.get("X-CSRFToken", "")
        == expected_csrf_header
    )


def test_install_username_prompt_password_env_var(
    mock_install_client, app_tarball: Path, monkeypatch
):
    monkeypatch.setenv("PHANTOM_PASSWORD", "test_password")
    result = runner.invoke(
        package,
        [
            "install",
            app_tarball.as_posix(),
            "https://10.1.23.4",
        ],
        input="admin",
    )
    assert result.exit_code == 0


def test_install_command_with_post_error(mock_install_client, app_tarball: Path):
    mock_install_client.post("app_install").respond(
        json={"status": "failed"}, status_code=403
    )

    result = runner.invoke(
        package,
        [
            "install",
            app_tarball.as_posix(),
            "10.1.23.4",
            "--username",
            "admin",
        ],
        input="test_password",
    )

    assert result.exit_code != 0


def test_install_incorrect_file_path():
    result = runner.invoke(package, ["install", "random", "10.1.23.4"])
    assert result.exit_code != 0


def test_install_app_tarball_not_file():
    example_app = Path.cwd() / "tests/example_app"
    result = runner.invoke(package, ["install", example_app.as_posix(), "10.1.23.4"])
    assert result.exit_code != 0


@pytest.mark.asyncio
@respx.mock
async def test_csrf_token_missing():
    respx.get("https://10.1.23.4/").respond(status_code=200)
    with pytest.raises(RuntimeError, match="Could not obtain CSRF token"):
        async with phantom_get_login_session("https://10.1.23.4", "admin", "password"):
            pass


@pytest.mark.asyncio
async def test_csrf_token_not_in_cookies():
    async with httpx.AsyncClient(base_url="https://10.1.23.4") as client:
        with pytest.raises(RuntimeError, match="CSRF token not found"):
            await phantom_install_app(client, "/app_install", {"file": b"test"})


def test_package_build_with_app_templates(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    assert result.exit_code == 0
    assert "Adding app templates to package" in result.stdout

    # Verify templates are in the tarball
    with tarfile.open(destination, "r:gz") as tar:
        members = tar.getnames()
        assert any("templates/reverse_string.html" in name for name in members)


def test_package_build_with_sdk_templates(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

        assert result.exit_code == 0
        assert "Adding SDK base template to package" in result.stdout

        with tarfile.open(destination, "r:gz") as tar:
            members = tar.getnames()
            # Check for the specific base template file
            assert any("templates/base/base_template.html" in name for name in members)


def test_package_build_without_app_templates(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
        patch("soar_sdk.cli.package.cli.APP_TEMPLATES") as mock_app_templates,
    ):
        # Mock APP_TEMPLATES to not exist
        mock_app_templates.exists.return_value = False

        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    assert result.exit_code == 0
    # Should NOT contain the app templates message
    assert "Adding app templates to package" not in result.stdout
    assert "Adding SDK base template to package" in result.stdout


def test_uv_lock_matches_declared_index():
    """Test that uv.lock contains wheel URLs matching the app's declared uv_index.

    This integration test verifies that when an app declares a uv_index in pyproject.toml,
    the uv.lock file contains wheel URLs consistent with that index declaration.
    For PyPI, wheels come from files.pythonhosted.org (PyPI's CDN).
    For custom indexes, wheels would come from that custom index's domain.
    """
    # Use the example app which has both pyproject.toml and uv.lock
    example_app = Path.cwd() / "tests/example_app"

    # Read the declared index from pyproject.toml
    with (example_app / "pyproject.toml").open() as f:
        pyproject = toml.load(f)

    declared_index = pyproject["tool"]["uv"]["index"][0]["url"]

    # Read the uv.lock file
    with (example_app / "uv.lock").open() as f:
        uv_lock = toml.load(f)

    # Verify that at least some packages have wheel URLs
    packages_with_wheels = [
        pkg
        for pkg in uv_lock.get("package", [])
        if pkg.get("wheels") and any("url" in wheel for wheel in pkg["wheels"])
    ]

    assert len(packages_with_wheels) > 0, (
        "uv.lock should contain packages with wheel URLs"
    )

    # For PyPI (the default), wheel URLs should come from PyPI's CDN (files.pythonhosted.org)
    # This verifies that the declared index in pyproject.toml is being used by uv
    if "pypi.python.org" in declared_index or "pypi.org" in declared_index:
        # Check a few packages to ensure they have PyPI CDN URLs
        for pkg in packages_with_wheels[:3]:  # Check first 3 packages
            for wheel in pkg["wheels"]:
                if "url" in wheel:
                    wheel_url = wheel["url"]
                    # PyPI wheels come from files.pythonhosted.org
                    assert (
                        "files.pythonhosted.org" in wheel_url or "pypi.org" in wheel_url
                    ), f"Package {pkg['name']}: Expected PyPI CDN URL, got: {wheel_url}"
                    break
    else:
        # For custom indexes, verify wheel URLs come from that index's domain
        declared_domain = urlparse(declared_index).netloc
        for pkg in packages_with_wheels[:3]:
            for wheel in pkg["wheels"]:
                if "url" in wheel:
                    wheel_url = wheel["url"]
                    wheel_domain = urlparse(wheel_url).netloc
                    assert declared_domain in wheel_domain, (
                        f"Package {pkg['name']}: Expected custom index domain {declared_domain}, got: {wheel_url}"
                    )
                    break


def test_package_build_fetches_from_custom_index(wheel_resp_mock, tmp_path: Path):
    """Test that package building fetches wheels from the declared custom index.

    This test verifies that when building a package, wheels are fetched from the
    index URLs specified in the uv.lock file, and the process completes successfully.
    """
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    assert result.exit_code == 0
    assert destination.is_file()
    # Verify that wheel downloads were attempted (mocked by wheel_resp_mock)
    assert wheel_resp_mock.called


def test_package_build_fails_with_clear_error_on_fetch_failure(
    respx_mock, tmp_path: Path
):
    """Test that package building produces a comprehensible error when wheel fetching fails.

    This test verifies that when a wheel cannot be fetched (due to connectivity issues,
    authentication failures, or other network problems), the error message is clear
    and actionable for the user.
    """
    example_app = Path.cwd() / "tests/example_app"

    # Mock wheel downloads to return 403 Forbidden
    wheel_route = respx_mock.get(url__regex=r".+/.+\.whl")
    wheel_route.respond(
        status_code=403, json={"error": "Forbidden - authentication required"}
    )

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    # The build should fail with a non-zero exit code
    assert result.exit_code != 0

    # The error message should be comprehensible and mention the issue
    # It should contain information about the HTTP error
    output = result.stdout + str(getattr(result, "exception", ""))
    assert "403" in output or "Forbidden" in output


def test_package_build_fails_with_clear_error_on_connection_timeout(
    respx_mock, tmp_path: Path
):
    """Test that package building produces a clear error when connection times out.

    This test verifies that network timeout errors are handled gracefully with
    user-friendly error messages.
    """
    example_app = Path.cwd() / "tests/example_app"

    # Mock wheel downloads to raise a timeout error
    wheel_route = respx_mock.get(url__regex=r".+/.+\.whl")
    wheel_route.side_effect = httpx.ReadTimeout("Connection timed out")

    with (
        context_directory(tmp_path),
        patch.object(UvWheel, "validate_hash", return_value=None),
    ):
        result = runner.invoke(
            package,
            [
                "build",
                example_app.as_posix(),
            ],
        )

    # The build should fail
    assert result.exit_code != 0

    # Error should mention timeout or connection issue
    output = result.stdout + str(getattr(result, "exception", ""))
    assert "timeout" in output.lower() or "connection" in output.lower()
