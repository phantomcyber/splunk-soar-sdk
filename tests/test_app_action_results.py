from unittest import mock

import phantom.app as phantom
from phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.action_results import ActionResult, ErrorActionResult, SuccessActionResult
from soar_sdk.app import App


def test_app_action_called_with_legacy_result_set(example_app, simple_action_input):
    action_result = example_app.manager.soar_client.add_action_result(
        PhantomActionResult(dict())
    )
    mock_function = mock.Mock(
        return_value=action_result.set_status(
            phantom.APP_SUCCESS, "Testing function run"
        )
    )
    example_app.manager._actions["test_connectivity"] = mock_function

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_app_action_called_with_new_single_result_set(example_app, simple_action_input):
    action_result = ActionResult(True, "Testing function run")
    mock_function = mock.Mock(return_value=action_result)
    example_app.manager._actions["test_connectivity"] = mock_function

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_app_action_called_with_returned_simple_result(
    example_app, simple_action_input
):
    mock_function = mock.Mock(return_value=(True, "Testing function run"))
    example_app.manager._actions["test_connectivity"] = mock_function

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_app_action_called_with_returned_success_result(
    example_app, simple_action_input
):
    mock_function = mock.Mock(return_value=SuccessActionResult("Testing function run"))
    example_app.manager._actions["test_connectivity"] = mock_function

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_app_action_called_with_returned_error_result(example_app, simple_action_input):
    mock_function = mock.Mock(
        return_value=ErrorActionResult("Testing function run error")
    )

    example_app.manager._actions["test_connectivity"] = mock_function

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1


def test_app_action_called_with_multiple_results_set(
    example_app: App, simple_action_input
):
    soar_client = example_app.manager.soar_client
    action_result1 = ActionResult(True, "Testing function run 1")
    soar_client.add_result(action_result1)
    action_result2 = ActionResult(True, "Testing function run 2")
    soar_client.add_result(action_result2)

    mock_function = mock.Mock(return_value=(True, "Multiple action results returned"))

    example_app.manager.set_action("test_connectivity", mock_function)

    example_app.handle(simple_action_input, None)

    assert mock_function.call_count == 1
    assert len(soar_client.get_action_results()) == 3
