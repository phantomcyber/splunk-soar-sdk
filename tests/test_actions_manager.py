from unittest import mock

from soar_sdk.app import App
from soar_sdk.connector import AppConnector
from soar_sdk.params import Params


def test_get_action(simple_app: App):
    @simple_app.action()
    def some_action(params: Params):
        pass

    assert simple_app.manager.get_action("some_action") is some_action


def test_get_actions(simple_app: App):
    @simple_app.action()
    def some_action(params: Params):
        pass

    assert simple_app.manager.get_actions() == {"some_action": some_action}


def test_debug(example_manager):
    with mock.patch.object(AppConnector, attribute="debug_print") as mocked:
        example_manager.soar_client.debug("Test", "Debug printing data")
        assert mocked.called


def test_get_soar_base_url(example_manager):
    with mock.patch.object(
        AppConnector, attribute="get_soar_base_url", return_value="some_url"
    ):
        assert example_manager.soar_client.get_soar_base_url() == "some_url"


def test_get_results(example_manager):
    with mock.patch.object(
        AppConnector, attribute="get_action_results", return_value=[]
    ):
        assert example_manager.soar_client.get_results() == []
