from unittest import mock

from soar_sdk.app import App


def test_app_run(example_app):
    with mock.patch("soar_sdk.app_runner.AppRunner.run") as run_mock:
        example_app.run()

    assert run_mock.called


def test_handle(example_app: App):
    with mock.patch.object(example_app.actions_provider, "handle") as mock_handle:
        example_app.handle(mock.Mock())

    mock_handle.assert_called_once()
