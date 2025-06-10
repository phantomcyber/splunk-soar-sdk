from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package
from soar_sdk.meta.dependencies import UvWheel

from soar_sdk.cli.path_utils import context_directory

import tarfile

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

    assert result.exit_code == 0
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

    assert mock_install_client.get("login").called
    assert mock_install_client.post("login").called
    assert mock_install_client.post("app_install").called

    app_install_call = mock_install_client.post("app_install")
    assert app_install_call.call_count == 1
    expected_cookies = "csrftoken=fake_csrf_token; sessionid=fake_session_id"
    assert (
        app_install_call.calls[0].request.headers.get("Cookie", "") == expected_cookies
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
