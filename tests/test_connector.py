from unittest import mock

from soar_sdk.connector import AppConnector


def test_connector_handle_sets_actions_and_runs_internal_handle(app_connector):
    app_connector._handle_action = mock.Mock()  # type: ignore[method-assign]

    app_connector.actions_manager.set_action("action_handler1", mock.Mock())
    app_connector.actions_manager.set_action("action_handler2", mock.Mock())

    in_json = "{}"

    app_connector.handle(in_json, None)  # type: ignore[arg-type]

    assert app_connector._handle_action.call_count == 1


def test_connector_handle_action_runs_action_from_handlers(app_connector):
    mocked_handler = mock.Mock()

    app_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="testing_handler"
    )
    app_connector.actions_manager.get_actions = mock.Mock(
        return_value={"testing_handler": mocked_handler}
    )

    app_connector.handle_action({})

    assert mocked_handler.call_count == 1


def test_connector_handle_action_handler_not_existing(app_connector):
    app_connector.get_action_identifier = mock.Mock(  # type: ignore[method-assign]
        return_value="not_existing_handler"
    )

    assert app_connector.handle_action({}) == (
        False,
        "Missing handler for action not_existing_handler",
    )


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
