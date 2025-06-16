from unittest import mock

import pytest

from soar_sdk.input_spec import InputSpecification
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult, ErrorActionResult, SuccessActionResult
from soar_sdk.actions_manager import (
    ActionsManager,
    _INGEST_STATE_KEY,
    _AUTH_STATE_KEY,
    _CACHE_STATE_KEY,
)
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from tests.stubs import SampleActionParams


def test_get_action(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_manager.get_action("some_action") is some_action


def test_get_actions(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_manager.get_actions() == {"some_action": some_action}


def test_get_actions_meta_list(simple_app: App):
    @simple_app.action()
    def some_action(params: Params, client) -> ActionOutput:
        pass

    assert simple_app.actions_manager.get_actions_meta_list() == [some_action.meta]


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
    @example_app.action()
    def test_action(params: Params, soar: SOARClient) -> ActionOutput:
        action_result1 = ActionResult(True, "Testing function run 1")
        action_result2 = ActionResult(True, "Testing function run 2")
        example_app.actions_manager.add_result(action_result1)
        example_app.actions_manager.add_result(action_result2)
        return True, "Multiple action results set"

    example_app.handle(simple_action_input.json())

    assert len(example_app.actions_manager.get_results()) == 3


def test_actions_provider_running_undefined_action(
    example_provider, simple_action_input
):
    example_provider._actions = {}

    with pytest.raises(RuntimeError):
        example_provider.handle(simple_action_input)


def test_app_connector_handle_action_runs_app_action(
    app_actions_manager: ActionsManager,
):
    mocked_handler = mock.Mock()

    app_actions_manager.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="testing_handler"
    )
    app_actions_manager.get_actions = mock.Mock(
        return_value={"testing_handler": mocked_handler}
    )

    app_actions_manager.handle_action({})

    assert mocked_handler.call_count == 1


def test_handle_action_handler_not_existing(app_actions_manager: ActionsManager):
    app_actions_manager.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="not_existing_handler"
    )

    with pytest.raises(RuntimeError):
        app_actions_manager.handle_action({})


def test_handle_raises_validation_error(
    app_actions_manager: ActionsManager,
):
    testing_handler = mock.Mock()
    testing_handler.meta.parameters = SampleActionParams

    app_actions_manager.get_action_identifier = mock.Mock()
    app_actions_manager.get_action = mock.Mock(return_value=testing_handler)
    app_actions_manager.save_progress = mock.Mock()

    app_actions_manager.handle_action({"field1": "five"})
    assert app_actions_manager.save_progress.call_count == 1


def test_app_connector_delegates_get_phantom_base_url():
    with mock.patch.object(
        ActionsManager,
        attribute="_get_phantom_base_url",
        return_value="some_url",
    ):
        assert ActionsManager.get_soar_base_url() == "some_url"


def test_app_connector_initialize_loads_state(app_actions_manager: ActionsManager):
    """Test that initialize loads the state from load_state method."""
    # Mock the load_state method to return a specific state
    test_state_inner = {"test_key": "test_value"}
    test_state = {
        _INGEST_STATE_KEY: test_state_inner,
        _AUTH_STATE_KEY: test_state_inner,
        _CACHE_STATE_KEY: test_state_inner,
    }

    app_actions_manager.load_state = mock.Mock(return_value=test_state)

    # Call initialize
    result = app_actions_manager.initialize()

    # Verify initialize returns True
    assert result is True

    # Verify load_state was called
    app_actions_manager.load_state.assert_called_once()

    # Verify the state was stored correctly
    assert app_actions_manager.ingestion_state == test_state_inner
    assert app_actions_manager.auth_state == test_state_inner
    assert app_actions_manager.asset_cache == test_state_inner


def test_app_connector_initialize_handles_empty_state(
    app_actions_manager: ActionsManager,
):
    """Test that initialize handles None return from load_state."""
    # Mock the load_state method to return None
    app_actions_manager.load_state = mock.Mock(return_value=None)

    # Call initialize
    result = app_actions_manager.initialize()

    # Verify initialize returns True
    assert result is True

    # Verify load_state was called
    app_actions_manager.load_state.assert_called_once()

    # Verify the state was initialized to an empty dict
    assert app_actions_manager.ingestion_state == {}
    assert app_actions_manager.auth_state == {}
    assert app_actions_manager.asset_cache == {}


def test_app_connector_finalize_saves_state(app_actions_manager: ActionsManager):
    """Test that finalize saves the current state using save_state."""
    # Set up a test state
    test_state = {"key1": "value1", "key2": "value2"}
    app_actions_manager.ingestion_state = test_state
    app_actions_manager.auth_state = test_state
    app_actions_manager.asset_cache = test_state

    # Mock the save_state method
    app_actions_manager.save_state = mock.Mock()

    # Call finalize
    result = app_actions_manager.finalize()

    # Verify finalize returns True
    assert result is True

    # Verify save_state was called with the correct state
    app_actions_manager.save_state.assert_called_once_with(
        {
            _INGEST_STATE_KEY: test_state,
            _AUTH_STATE_KEY: test_state,
            _CACHE_STATE_KEY: test_state,
        }
    )


def test_app_connector_delegates_set_csrf_info(app_actions_manager: ActionsManager):
    app_actions_manager._set_csrf_info = mock.Mock()  # type: ignore[method-assign]

    app_actions_manager.set_csrf_info("", "")

    assert app_actions_manager._set_csrf_info.call_count == 1
