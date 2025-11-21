from unittest import mock

from typer.testing import CliRunner

from soar_sdk.cli import cli

runner = CliRunner()


def test_unit_command_basic():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit"])
        assert result.exit_code == 0
        assert mock_run.called


def test_unit_command_with_coverage():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit", "--coverage"])
        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "--no-cov" not in call_args


def test_unit_command_with_test_path():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit", "-t", "tests/test_foo.py"])
        assert result.exit_code == 0


def test_unit_command_no_parallel():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit", "--no-parallel"])
        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "-n" not in call_args


def test_unit_command_verbose():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit", "--verbose"])
        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args


def test_unit_command_junit_xml():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(cli.app, ["test", "unit", "--junit-xml", "results.xml"])
        assert result.exit_code == 0


def test_unit_command_failure():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=1)
        result = runner.invoke(cli.app, ["test", "unit"])
        assert result.exit_code == 1


def test_unit_command_keyboard_interrupt():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt()
        result = runner.invoke(cli.app, ["test", "unit"])
        assert result.exit_code == 130


def test_integration_command_basic():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app, ["test", "integration", "10.1.19.88", "-u", "admin", "-p", "pass"]
        )
        assert result.exit_code == 0
        assert mock_run.called


def test_integration_command_missing_username():
    result = runner.invoke(cli.app, ["test", "integration", "10.1.19.88"])
    assert result.exit_code == 1


def test_integration_command_missing_password():
    result = runner.invoke(
        cli.app, ["test", "integration", "10.1.19.88", "-u", "admin"]
    )
    assert result.exit_code == 1


def test_integration_command_with_automation_broker():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app,
            [
                "test",
                "integration",
                "10.1.19.88",
                "-u",
                "admin",
                "-p",
                "pass",
                "--automation-broker",
                "my-broker",
            ],
        )
        assert result.exit_code == 0


def test_integration_command_force_automation_broker():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app,
            [
                "test",
                "integration",
                "10.1.19.88",
                "-u",
                "admin",
                "-p",
                "pass",
                "--force-automation-broker",
            ],
        )
        assert result.exit_code == 0


def test_integration_command_verbose():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app,
            [
                "test",
                "integration",
                "10.1.19.88",
                "-u",
                "admin",
                "-p",
                "pass",
                "--verbose",
            ],
        )
        assert result.exit_code == 0


def test_integration_command_test_path():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app,
            [
                "test",
                "integration",
                "10.1.19.88",
                "-u",
                "admin",
                "-p",
                "pass",
                "-t",
                "tests/integration/test_foo.py",
            ],
        )
        assert result.exit_code == 0


def test_integration_command_junit_xml():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        result = runner.invoke(
            cli.app,
            [
                "test",
                "integration",
                "10.1.19.88",
                "-u",
                "admin",
                "-p",
                "pass",
                "--junit-xml",
                "results.xml",
            ],
        )
        assert result.exit_code == 0


def test_integration_command_failure():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=1)
        result = runner.invoke(
            cli.app, ["test", "integration", "10.1.19.88", "-u", "admin", "-p", "pass"]
        )
        assert result.exit_code == 1


def test_integration_command_keyboard_interrupt():
    with mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt()
        result = runner.invoke(
            cli.app, ["test", "integration", "10.1.19.88", "-u", "admin", "-p", "pass"]
        )
        assert result.exit_code == 130
