from unittest import mock

import pytest

from soar_sdk.input_spec import InputSpecification
import soar_sdk.shims.phantom.app as phantom
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult, ErrorActionResult, SuccessActionResult
from soar_sdk.actions_provider import ActionsProvider
from soar_sdk.app import App
from soar_sdk.connector import AppConnector
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput


def test_actions_provider_adapts_legacy_connector():
    provider = ActionsProvider(legacy_connector_class=mock.Mock)

    assert provider.legacy_soar_client is not None
    assert isinstance(provider.legacy_soar_client, SOARClient)


def test_get_action(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_provider.get_action("some_action") is some_action


def test_get_actions(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_provider.get_actions() == {"some_action": some_action}


def test_get_actions_meta_list(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_provider.get_actions_meta_list() == [some_action.meta]


def test_debug(example_provider):
    with mock.patch.object(AppConnector, attribute="debug_print") as mocked:
        example_provider.soar_client.debug("Test", "Debug printing data")
        assert mocked.called


def test_error(example_provider):
    with mock.patch.object(AppConnector, attribute="error_print") as mocked:
        example_provider.soar_client.error("Test", "Error printing data")
        assert mocked.called


def test_get_soar_base_url(example_provider):
    with mock.patch.object(
        AppConnector, attribute="get_soar_base_url", return_value="some_url"
    ):
        assert example_provider.soar_client.get_soar_base_url() == "some_url"


def test_get_results(example_provider):
    with mock.patch.object(
        AppConnector, attribute="get_action_results", return_value=[]
    ):
        assert example_provider.soar_client.get_results() == []


def test_action_called_with_legacy_result_set(example_provider, simple_action_input):
    action_result = example_provider.soar_client.add_action_result(
        PhantomActionResult(dict())
    )
    mock_function = mock.Mock(
        return_value=action_result.set_status(
            phantom.APP_SUCCESS, "Testing function run"
        )
    )
    example_provider._actions["test_action"] = mock_function

    example_provider.handle(simple_action_input)

    assert mock_function.call_count == 1


def test_action_called_with_new_single_result_set(
    example_provider, simple_action_input
):
    action_result = ActionResult(True, "Testing function run")
    mock_function = mock.Mock(return_value=action_result)
    example_provider._actions["test_action"] = mock_function

    example_provider.handle(simple_action_input)

    assert mock_function.call_count == 1


def test_action_called_with_returned_simple_result(
    example_provider, simple_action_input
):
    mock_function = mock.Mock(return_value=(True, "Testing function run"))
    example_provider._actions["test_action"] = mock_function

    example_provider.handle(simple_action_input)

    assert mock_function.call_count == 1


def test_action_called_with_returned_success_result(
    example_provider, simple_action_input
):
    mock_function = mock.Mock(return_value=SuccessActionResult("Testing function run"))
    example_provider._actions["test_action"] = mock_function

    example_provider.handle(simple_action_input)

    assert mock_function.call_count == 1


def test_action_called_with_returned_error_result(
    example_provider, simple_action_input
):
    mock_function = mock.Mock(
        return_value=ErrorActionResult("Testing function run error")
    )

    example_provider._actions["test_action"] = mock_function

    example_provider.handle(simple_action_input)

    assert mock_function.call_count == 1


def test_action_called_with_multiple_results_set(
    example_app: App, simple_action_input: InputSpecification
):
    # FIXME: this is phantom_lib integration check and should be moved from here
    soar = example_app.actions_provider.soar_client

    @example_app.action()
    def test_action(params: Params, soar: SOARClient) -> ActionOutput:
        action_result1 = ActionResult(True, "Testing function run 1")
        action_result2 = ActionResult(True, "Testing function run 2")
        soar.add_result(action_result1)
        soar.add_result(action_result2)
        return True, "Multiple action results set"

    example_app.handle(simple_action_input.json())

    assert len(soar.get_action_results()) == 3


def test_actions_provider_running_legacy_handler(example_provider, simple_action_input):
    example_provider._actions = {}
    example_provider.legacy_soar_client = mock.Mock()
    example_provider.legacy_soar_client.handle = mock.Mock()

    example_provider.handle(simple_action_input)

    assert example_provider.legacy_soar_client.handle.call_count == 1


def test_actions_provider_running_undefined_action(
    example_provider, simple_action_input
):
    example_provider._actions = {}
    example_provider.legacy_soar_client = None

    with pytest.raises(RuntimeError):
        example_provider.handle(simple_action_input)
