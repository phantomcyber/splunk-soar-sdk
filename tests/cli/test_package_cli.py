from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package
from soar_sdk.meta.dependencies import UvWheel
from soar_sdk.cli.package import cli
from soar_sdk.cli.package import utils
import tempfile

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
        self.get_patcher = patch.object(utils.requests.Session, "get")
        self.post_patcher = patch.object(utils.requests.Session, "post")

        self.mock_get = self.get_patcher.start()
        self.addCleanup(self.get_patcher.stop)
        self.mock_post = self.post_patcher.start()
        self.addCleanup(self.post_patcher.stop)

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
        self.mock_prompt_patcher = patch.object(cli.typer, attribute="prompt")
        self.mock_prompt = self.mock_prompt_patcher.start()
        self.addCleanup(self.mock_prompt_patcher.stop)
        self.mock_prompt.return_value = "test_password_or_username"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".tgz") as temp_tgz:
            self.temp_tgz_path = Path(temp_tgz.name)

    def tearDown(self):
        if self.temp_tgz_path.exists():
            self.temp_tgz_path.unlink()

    def test_install_command(self):
        result = runner.invoke(
            package,
            [
                "install",
                self.temp_tgz_path.as_posix(),
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
        with patch.dict("os.environ", {"PHANTOM_PASSWORD": "test_password"}):
            result = runner.invoke(
                package,
                [
                    "install",
                    self.temp_tgz_path.as_posix(),
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

        result = runner.invoke(
            package,
            [
                "install",
                self.temp_tgz_path.as_posix(),
                "10.1.23.4",
                "--username",
                "admin",
            ],
        )

        assert result.exit_code != 0


def test_install_incorrect_file_path():
    result = runner.invoke(package, ["install", "random", "10.1.23.4"])
    assert result.exit_code != 0


def test_install_app_tarball_not_file():
    example_app = Path.cwd() / "tests/example_app"
    result = runner.invoke(package, ["install", example_app.as_posix(), "10.1.23.4"])
    assert result.exit_code != 0


def test_install_app_tarball_not_tgz_file():
    example_app = Path.cwd() / "tests/example_app/app.json"
    result = runner.invoke(package, ["install", example_app.as_posix(), "10.1.23.4"])
    assert result.exit_code != 0
