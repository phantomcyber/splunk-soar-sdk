from unittest import mock

import pytest

import phantom.app as phantom
from phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult, ErrorActionResult, SuccessActionResult
from soar_sdk.actions_manager import ActionsManager
from soar_sdk.app import App
from soar_sdk.connector import AppConnector
from soar_sdk.params import Params


def test_actions_manager_adapts_legacy_connector():
    manager = ActionsManager(legacy_connector_class=mock.Mock)

    assert manager.legacy_soar_client is not None
    assert isinstance(manager.legacy_soar_client, SOARClient)


def test_get_action(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client):
        pass

    assert simple_app.manager.get_action("some_action") is some_action


def test_get_actions(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client):
        pass

    assert simple_app.manager.get_actions() == {"some_action": some_action}


def test_get_actions_meta_list(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client):
        pass

    assert simple_app.manager.get_actions_meta_list() == [some_action.meta]


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


def test_action_called_with_legacy_result_set(example_manager, simple_action_input):
    action_result = example_manager.soar_client.add_action_result(
        PhantomActionResult(dict())
    )
    mock_function = mock.Mock(
        return_value=action_result.set_status(
            phantom.APP_SUCCESS, "Testing function run"
        )
    )
    example_manager._actions["test_connectivity"] = mock_function

    example_manager.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_action_called_with_new_single_result_set(example_manager, simple_action_input):
    action_result = ActionResult(True, "Testing function run")
    mock_function = mock.Mock(return_value=action_result)
    example_manager._actions["test_connectivity"] = mock_function

    example_manager.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_action_called_with_returned_simple_result(
    example_manager, simple_action_input
):
    mock_function = mock.Mock(return_value=(True, "Testing function run"))
    example_manager._actions["test_connectivity"] = mock_function

    example_manager.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_action_called_with_returned_success_result(
    example_manager, simple_action_input
):
    mock_function = mock.Mock(return_value=SuccessActionResult("Testing function run"))
    example_manager._actions["test_connectivity"] = mock_function

    example_manager.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_action_called_with_returned_error_result(example_manager, simple_action_input):
    mock_function = mock.Mock(
        return_value=ErrorActionResult("Testing function run error")
    )

    example_manager._actions["test_connectivity"] = mock_function

    example_manager.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_action_called_with_multiple_results_set(example_app, simple_action_input):
    # FIXME: this is phantom_lib integration check and should be moved from here
    client = example_app.manager.soar_client

    @example_app.action()
    def test_connectivity(params: Params, client: SOARClient):
        action_result1 = ActionResult(True, "Testing function run 1")
        action_result2 = ActionResult(True, "Testing function run 2")
        client.add_result(action_result1)
        client.add_result(action_result2)
        return True, "Multiple action results set"

    example_app.handle(simple_action_input)

    assert len(client.get_action_results()) == 3


def test_actions_manager_running_legacy_handler(example_manager, simple_action_input):
    example_manager._actions = {}
    example_manager.legacy_soar_client = mock.Mock()
    example_manager.legacy_soar_client.handle = mock.Mock()

    example_manager.handle(simple_action_input)

    assert example_manager.legacy_soar_client.handle.call_count == 1


def test_actions_manager_running_undefined_action(example_manager, simple_action_input):
    example_manager._actions = {}
    example_manager.legacy_soar_client = None

    with pytest.raises(RuntimeError):
        example_manager.handle(simple_action_input)
