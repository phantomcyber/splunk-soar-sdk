import pytest
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.exceptions import AssetMisconfiguration
from unittest import mock


def test_connectivity_decoration_fails_when_used_more_than_once(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient):
        pass

    with pytest.raises(TypeError) as exception_info:

        @simple_app.test_connectivity()
        def test_connectivity2(client: SOARClient):
            pass

    assert (
        "The 'test_connectivity' decorator can only be used once per App instance."
        in str(exception_info)
    )


def test_connectivity_decoration_with_meta(simple_app):
    @simple_app.test_connectivity()
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
        simple_app.actions_provider.get_action("test_connectivity") == test_connectivity
    )


def test_connectivity_returns_not_none(simple_app):
    with pytest.raises(TypeError) as exception_info:

        @simple_app.test_connectivity()
        def test_connectivity(client: SOARClient) -> ActionOutput:
            return ActionOutput(bool=True)

    assert (
        "Test connectivity function must not return any value (return type should be None)."
        in str(exception_info)
    )


def test_connectivity_raises_with_no_type_hint(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient):
        return ActionOutput(bool=True)

    client_mock = mock.Mock()
    result = test_connectivity(client=client_mock)
    assert not result
    assert client_mock.add_result.call_count == 1


def test_connectivity_bubbles_up_errors(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient):
        raise RuntimeError("Test connectivity failed")

    client_mock = mock.Mock()

    result = test_connectivity(client=client_mock)
    assert not result
    assert client_mock.add_exception.call_count == 1
    assert client_mock.add_result.call_count == 1


def test_connectivity_run(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient) -> None:
        assert True

    assert test_connectivity()


def test_connectivity_action_failed(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient) -> None:
        raise AssetMisconfiguration("Test connectivity failed")

    client_mock = mock.Mock()
    result = test_connectivity(client=client_mock)
    assert not result
    assert client_mock.add_result.call_count == 1
