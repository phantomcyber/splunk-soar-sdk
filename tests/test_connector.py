from unittest import mock

import pytest

from soar_sdk.connector import (
    AppConnector,
    _INGEST_STATE_KEY,
    _AUTH_STATE_KEY,
    _CACHE_STATE_KEY,
)
from soar_sdk.input_spec import InputSpecification
from tests.stubs import SampleActionParams


def test_app_connector_handle_runs_legacy__handle_action(
    app_connector: AppConnector, simple_action_input: InputSpecification
):
    app_connector.actions_provider.set_action("action_handler1", mock.Mock())
    app_connector.actions_provider.set_action("action_handler2", mock.Mock())

    with mock.patch.object(app_connector, "_handle_action") as mock_handle_action:
        app_connector.handle(simple_action_input)
        assert mock_handle_action.call_count == 1


def test_app_connector_handle_action_runs_app_action(app_connector: AppConnector):
    mocked_handler = mock.Mock()

    app_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="testing_handler"
    )
    app_connector.actions_provider.get_actions = mock.Mock(
        return_value={"testing_handler": mocked_handler}
    )

    app_connector.handle_action({})

    assert mocked_handler.call_count == 1


def test_app_connector_handle_action_handler_not_existing(app_connector: AppConnector):
    app_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="not_existing_handler"
    )

    with pytest.raises(RuntimeError):
        app_connector.handle_action({})


def test_app_connector_action_handle_raises_validation_error(
    app_connector: AppConnector,
):
    testing_handler = mock.Mock()
    testing_handler.meta.parameters = SampleActionParams

    app_connector.get_action_identifier = mock.Mock()
    app_connector.actions_provider.get_action = mock.Mock(return_value=testing_handler)
    app_connector.save_progress = mock.Mock()

    app_connector.handle_action({"field1": "five"})
    assert app_connector.save_progress.call_count == 1


def test_app_connector_delegates_get_phantom_base_url():
    with mock.patch.object(
        AppConnector,
        attribute="_get_phantom_base_url",
        return_value="some_url",
    ):
        assert AppConnector.get_soar_base_url() == "some_url"


def test_app_connector_delegates_set_csrf_info(simple_connector: AppConnector):
    simple_connector._set_csrf_info = mock.Mock()  # type: ignore[method-assign]

    simple_connector.set_csrf_info("", "")

    assert simple_connector._set_csrf_info.call_count == 1


def test_app_connector_initialize_loads_state(simple_connector: AppConnector):
    """Test that initialize loads the state from load_state method."""
    # Mock the load_state method to return a specific state
    test_state_inner = {"test_key": "test_value"}
    test_state = {
        _INGEST_STATE_KEY: test_state_inner,
        _AUTH_STATE_KEY: test_state_inner,
        _CACHE_STATE_KEY: test_state_inner,
    }

    simple_connector.load_state = mock.Mock(return_value=test_state)

    # Call initialize
    result = simple_connector.initialize()

    # Verify initialize returns True
    assert result is True

    # Verify load_state was called
    simple_connector.load_state.assert_called_once()

    # Verify the state was stored correctly
    assert simple_connector.ingestion_state == test_state_inner
    assert simple_connector.auth_state == test_state_inner
    assert simple_connector.asset_cache == test_state_inner


def test_app_connector_initialize_handles_empty_state(simple_connector: AppConnector):
    """Test that initialize handles None return from load_state."""
    # Mock the load_state method to return None
    simple_connector.load_state = mock.Mock(return_value=None)

    # Call initialize
    result = simple_connector.initialize()

    # Verify initialize returns True
    assert result is True

    # Verify load_state was called
    simple_connector.load_state.assert_called_once()

    # Verify the state was initialized to an empty dict
    assert simple_connector.ingestion_state == {}
    assert simple_connector.auth_state == {}
    assert simple_connector.asset_cache == {}


def test_app_connector_finalize_saves_state(simple_connector: AppConnector):
    """Test that finalize saves the current state using save_state."""
    # Set up a test state
    test_state = {"key1": "value1", "key2": "value2"}
    simple_connector.ingestion_state = test_state
    simple_connector.auth_state = test_state
    simple_connector.asset_cache = test_state

    # Mock the save_state method
    simple_connector.save_state = mock.Mock()

    # Call finalize
    result = simple_connector.finalize()

    # Verify finalize returns True
    assert result is True

    # Verify save_state was called with the correct state
    simple_connector.save_state.assert_called_once_with(
        {
            _INGEST_STATE_KEY: test_state,
            _AUTH_STATE_KEY: test_state,
            _CACHE_STATE_KEY: test_state,
        }
    )


def test_update_client(
    simple_connector: AppConnector,
    action_input_soar_auth: InputSpecification,
    mock_get_any_soar_call,
    mock_post_any_soar_call,
):
    simple_connector.update_client(action_input_soar_auth)
    assert mock_get_any_soar_call.call_count == 1
    request = mock_get_any_soar_call.calls[0].request
    assert request.url == "https://10.34.5.6/login"
    assert simple_connector.client.headers["X-CSRFToken"] == "mocked_csrf_token"

    assert mock_post_any_soar_call.call_count == 1
    post_request = mock_post_any_soar_call.calls[0].request
    assert post_request.url == "https://10.34.5.6/login"

    assert (
        simple_connector.client.headers["Cookie"]
        == "sessionid=mocked_session_id;csrftoken=mocked_csrf_token"
    )


def test_authenticate_soar_client_on_platform(
    simple_connector: AppConnector,
    action_input_soar_platform_auth: InputSpecification,
    mock_get_any_soar_call,
):
    simple_connector.authenticate_soar_client(action_input_soar_platform_auth)
    assert mock_get_any_soar_call.call_count == 1
