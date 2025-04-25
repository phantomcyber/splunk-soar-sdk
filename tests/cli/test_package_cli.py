from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

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


class TestInstallCommand(TestCase):
    def setUp(self):
        self.get_patcher = patch("soar_sdk.cli.package.utils.requests.Session.get")
        self.post_patcher = patch("soar_sdk.cli.package.utils.requests.Session.post")

        # Start the patches and save the mock objects
        self.mock_get = self.get_patcher.start()
        self.mock_post = self.post_patcher.start()

        self.mock_get_response = MagicMock()
        self.mock_get_response.cookies.get_dict.return_value = {
            "csrftoken": "mocked_csrf_token"
        }
        self.mock_get.return_value = self.mock_get_response

        self.mock_post_response = MagicMock()
        self.mock_post_response.cookies.get_dict.return_value = {
            "csrftoken": "mocked_csrf_token",
            "sessionid": "mocked_session_id",
        }
        self.mock_post.return_value = self.mock_post_response

        # Patch `typer.prompt`
        self.prompt_patcher = patch("typer.prompt")
        self.mock_prompt = self.prompt_patcher.start()
        self.mock_prompt.return_value = "test_password_or_username"

    def tearDown(self):
        # Stop all patches to ensure clean state for other tests
        self.get_patcher.stop()
        self.post_patcher.stop()

    def test_install_command(self):
        destination = Path.cwd() / "tests/cli/data" / "example.tgz"

        result = runner.invoke(
            package,
            [
                "install",
                destination.as_posix(),
                "10.1.23.4",
                "--username",
                "admin",
            ],
        )
        self.mock_prompt.assert_called_once()

        assert result.exit_code == 0

        self.mock_get.assert_called_once_with("https://10.1.23.4/login", verify=False)
        assert self.mock_post.call_count == 2
        self.mock_post.assert_any_call(
            "https://10.1.23.4/login",
            data={
                "username": "admin",
                "password": self.mock_prompt.return_value,
                "csrfmiddlewaretoken": "mocked_csrf_token",
            },
            verify=False,
            cookies=self.mock_get_response.cookies,
            headers={"Referer": "https://10.1.23.4/login"},
        )

    def test_install_username_prompt_password_env_var(self):
        destination = Path.cwd() / "tests/cli/data" / "example.tgz"

        with patch.dict("os.environ", {"PHANTOM_PASSWORD": "test_password"}):
            result = runner.invoke(
                package,
                [
                    "install",
                    destination.as_posix(),
                    "https://10.1.23.4",
                ],
            )
            self.mock_prompt.assert_called_once()

        assert result.exit_code == 0

    def test_install_command_with_post_error(self):
        self.mock_post_response.status_code = 400
        self.mock_post_response.raise_for_status.side_effect = Exception(
            "Simulated raise_for_status error"
        )
        self.mock_post.return_value = self.mock_post_response

        destination = Path.cwd() / "tests/cli/data" / "example.tgz"

        result = runner.invoke(
            package,
            [
                "install",
                destination.as_posix(),
                "10.1.23.4",
                "--username",
                "admin",
            ],
        )

        assert result.exit_code != 0

    def test_incorrect_file_path(self):
        result = runner.invoke(package, ["install", "random", "10.1.23.4"])
        assert result.exit_code != 0

    def test_app_tarball_not_file(self):
        example_app = Path.cwd() / "tests/example_app"
        result = runner.invoke(
            package, ["install", example_app.as_posix(), "10.1.23.4"]
        )
        assert result.exit_code != 0

    def test_app_tarball_not_tgz_file(self):
        example_app = Path.cwd() / "tests/example_app/app.json"
        result = runner.invoke(
            package, ["install", example_app.as_posix(), "10.1.23.4"]
        )
        assert result.exit_code != 0
