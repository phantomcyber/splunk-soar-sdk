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
