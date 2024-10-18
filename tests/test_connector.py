from unittest import mock

import phantom.app as phantom_app

from soar_sdk.connector import AppConnector


def test_connector_handle_sets_actions_and_runs_internal_handle(simple_connector):
    simple_connector._handle_action = mock.Mock()  # type: ignore[method-assign]

    simple_connector.app.set_action("action_handler1", mock.Mock())
    simple_connector.app.set_action("action_handler2", mock.Mock())

    in_json = "{}"

    simple_connector.handle(in_json, None)  # type: ignore[arg-type]

    assert simple_connector._handle_action.call_count == 1


def test_connector_handle_action_runs_action_from_handlers(simple_connector):
    mocked_handler = mock.Mock()

    simple_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="testing_handler"
    )
    simple_connector.app.get_actions = mock.Mock(
        return_value={"testing_handler": mocked_handler}
    )

    simple_connector.handle_action({})

    assert mocked_handler.call_count == 1


def test_connector_handle_action_handler_not_existing(simple_connector):
    simple_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="not_existing_handler"
    )

    assert simple_connector.handle_action({}) == phantom_app.APP_ERROR


def test_connector_get_phantom_base_url():
    with mock.patch.object(
        AppConnector,
        attribute="_get_phantom_base_url",
        return_value="some_url",
    ):
        assert AppConnector.get_soar_base_url() == "some_url"


def test_connector_set_csrf_info(simple_connector):
    simple_connector._set_csrf_info = mock.Mock()  # type: ignore[method-assign]

    simple_connector.set_csrf_info("", "")

    assert simple_connector._set_csrf_info.call_count == 1
