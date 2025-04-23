import pytest
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput


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


def test_connectivity_returns_with_no_type_hint(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient):
        return ActionOutput(bool=True)

    assert not test_connectivity()


def test_connectivity_raise_during_execution(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient):
        raise RuntimeError("Test connectivity failed")

    assert not test_connectivity()


def test_connectivity_run(simple_app):
    @simple_app.test_connectivity()
    def test_connectivity(client: SOARClient) -> None:
        assert True

    assert test_connectivity()
