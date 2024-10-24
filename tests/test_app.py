from unittest import mock

from soar_sdk.app import App
from soar_sdk.connector import AppConnector
from soar_sdk.params import Params


def test_app_initialization(simple_app):
    assert simple_app


def test_app_debug(example_app):
    with mock.patch.object(AppConnector, attribute="debug_print") as mocked:
        example_app.manager.debug("Test", "Debug printing data")
        assert mocked.called


def test_app_get_soar_base_url(example_app):
    with mock.patch.object(
        AppConnector, attribute="get_soar_base_url", return_value="some_url"
    ):
        assert example_app.get_soar_base_url() == "some_url"


def test_app_get_results(example_app):
    with mock.patch.object(
        AppConnector, attribute="get_action_results", return_value=[]
    ):
        assert example_app.get_results() == []


def test_app_run(example_app):
    with mock.patch("soar_sdk.app_runner.AppRunner.run") as run_mock:
        example_app.run()

    assert run_mock.called


def test_get_action(simple_app: App):
    @simple_app.action()
    def some_action(ctx, params: Params):
        pass

    assert simple_app.get_action("some_action") is some_action


def test_get_actions(simple_app: App):
    @simple_app.action()
    def some_action(ctx, params: Params):
        pass

    assert simple_app.get_actions() == {"some_action": some_action}
