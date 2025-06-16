import pytest
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.exceptions import AssetMisconfiguration
from unittest import mock
from soar_sdk.app import App


def test_connectivity_decoration_fails_when_used_more_than_once(app_with_action: App):
    @app_with_action.test_connectivity()
    def test_connectivity(soar: SOARClient):
        pass

    with pytest.raises(TypeError) as exception_info:

        @app_with_action.test_connectivity()
        def test_connectivity2(soar: SOARClient):
            pass

    assert (
        "The 'test_connectivity' decorator can only be used once per App instance."
        in str(exception_info)
    )


def test_connectivity_decoration_with_meta(app_with_action: App):
    @app_with_action.test_connectivity()
    def test_connectivity(params: SOARClient):
        """
        This action does nothing for now.
        """
        pass

    assert sorted(test_connectivity.meta.dict().keys()) == sorted(
        [
            "action",
            "identifier",
            "description",
            "verbose",
            "type",
            "parameters",
            "read_only",
            "output",
            "versions",
        ]
    )

    assert test_connectivity.meta.action == "test connectivity"
    assert test_connectivity.meta.description == "This action does nothing for now."
    assert (
        app_with_action.actions_manager.get_action("test_connectivity")
        == test_connectivity
    )


def test_connectivity_returns_not_none(app_with_action):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.test_connectivity()
        def test_connectivity(soar: SOARClient) -> ActionOutput:
            return ActionOutput(bool=True)

    assert (
        "Test connectivity function must not return any value (return type should be None)."
        in str(exception_info)
    )


def test_connectivity_raises_with_no_type_hint(app_with_action: App):
    @app_with_action.test_connectivity()
    def test_connectivity(soar: SOARClient):
        return ActionOutput(bool=True)

    app_with_action.actions_manager = mock.Mock()
    result = test_connectivity(soar=app_with_action.soar_client)
    assert not result
    assert app_with_action.actions_manager.add_result.call_count == 1


def test_connectivity_bubbles_up_errors(app_with_action: App):
    @app_with_action.test_connectivity()
    def test_connectivity(soar: SOARClient):
        raise RuntimeError("Test connectivity failed")

    app_with_action.actions_manager = mock.Mock()

    result = test_connectivity(soar=app_with_action.soar_client)
    assert not result
    assert app_with_action.actions_manager.add_exception.call_count == 1
    assert app_with_action.actions_manager.add_result.call_count == 1


def test_connectivity_run(app_with_action):
    @app_with_action.test_connectivity()
    def test_connectivity(soar: SOARClient) -> None:
        assert True

    assert test_connectivity()


def test_connectivity_action_failed(app_with_action: App):
    @app_with_action.test_connectivity()
    def test_connectivity(soar: SOARClient) -> None:
        raise AssetMisconfiguration("Test connectivity failed")

    app_with_action.actions_manager = mock.Mock()
    result = test_connectivity(soar=app_with_action.soar_client)
    assert not result
    assert app_with_action.actions_manager.add_result.call_count == 1
