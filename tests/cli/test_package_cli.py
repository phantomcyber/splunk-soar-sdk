from pathlib import Path
import tempfile

from typer.testing import CliRunner

from soar_sdk.cli.package.cli import package


runner = CliRunner()


def test_package_build_command():
    with tempfile.TemporaryDirectory() as tempdir:
        example_app = Path.cwd() / "tests/example_app"
        destination = Path(tempdir) / "example_app.tgz"

        result = runner.invoke(
            package, ["build", destination.as_posix(), example_app.as_posix()]
        )

        assert result.exit_code == 0
        assert destination.is_file()
