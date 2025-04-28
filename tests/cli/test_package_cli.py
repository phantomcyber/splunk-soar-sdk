from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package
from soar_sdk.meta.dependencies import UvWheel

runner = CliRunner()


def test_package_build_command(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    # Create the patch for hash validation
    with patch.object(UvWheel, "validate_hash", return_value=None):
        result = runner.invoke(
            package,
            [
                "build",
                destination.as_posix(),
                example_app.as_posix(),
            ],
        )

    assert result.exit_code == 0
    assert destination.is_file()
    # Verify our mock was called
    assert wheel_resp_mock.called


def test_package_build_command_with_sdk_wheel(wheel_resp_mock, tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    fake_wheel = tmp_path / "fake.whl"
    with fake_wheel.open("wb") as whl:
        whl.write(b"deadbeef")

    with patch.object(UvWheel, "validate_hash", return_value=None):
        result = runner.invoke(
            package,
            [
                "build",
                destination.as_posix(),
                example_app.as_posix(),
                "--with-sdk-wheel-from",
                fake_wheel.as_posix(),
            ],
        )

    assert result.exit_code == 0
    assert destination.is_file()
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


def test_install_command(mock_requests_session, app_tarball: Path):
    mock_get, mock_post = set_up_install_request_responses(mock_requests_session)

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

    mock_get.assert_called_once_with("https://10.1.23.4/login", verify=False)
    assert mock_post.call_count == 2
    mock_post.assert_any_call(
        "https://10.1.23.4/login",
        data={
            "username": "admin",
            "password": "test_password",
            "csrfmiddlewaretoken": "mocked_csrf_token",
        },
        verify=False,
        cookies=mock_get.return_value.cookies,
        headers={"Referer": "https://10.1.23.4/login"},
    )


def test_install_username_prompt_password_env_var(
    mock_requests_session, app_tarball: Path, monkeypatch
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


def test_install_command_with_post_error(mock_requests_session, app_tarball: Path):
    _, mock_post = set_up_install_request_responses(mock_requests_session)
    mock_post.return_value.raise_for_status.side_effect = Exception("Mocked error")

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
