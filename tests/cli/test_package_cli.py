from pathlib import Path

from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package


runner = CliRunner()


def test_package_build_command(tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

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


def test_package_build_command_with_sdk_wheel(tmp_path: Path):
    example_app = Path.cwd() / "tests/example_app"
    destination = tmp_path / "example_app.tgz"

    fake_wheel = tmp_path / "fake.whl"
    with fake_wheel.open("wb") as whl:
        whl.write(b"deadbeef")

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
