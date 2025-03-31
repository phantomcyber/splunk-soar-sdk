from unittest import mock

import pytest

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput
from tests.stubs import SampleActionParams, SampleNestedOutput, SampleOutput


class SampleParams(Params):
    int_value: int = Param(0, "Integer Value", data_type="numeric")
    str_value: str = Param(1, "String Value")
    pass_value: str = Param(2, "Password Value", data_type="password")
    bool_value: bool = Param(3, "Boolean Value", data_type="boolean")


@pytest.fixture
def sample_params() -> SampleParams:
    return SampleParams(
        int_value=1,
        str_value="test",
        pass_value="<PASSWORD>",
        bool_value=True,
    )


@pytest.fixture
def sample_output() -> SampleOutput:
    return SampleOutput(
        string_value="test",
        int_value=1,
        list_value=["a", "b"],
        bool_value=True,
        nested_value=SampleNestedOutput(bool_value=True),
    )


def test_action_decoration_fails_without_params(simple_app):
    with pytest.raises(TypeError) as exception_info:

        @simple_app.action()
        def action_function_no_params() -> ActionOutput:
            pass

    assert "Action function must accept at least the params" in str(exception_info)


def test_action_decoration_fails_without_params_type_set(simple_app):
    with pytest.raises(TypeError) as exception_info:

        @simple_app.action()
        def action_function_no_params_type(params) -> ActionOutput:
            pass

    assert "has no params type set" in str(exception_info)


def test_action_decoration_fails_with_params_not_inheriting_from_Params(simple_app):
    class SomeClass:
        pass

    with pytest.raises(TypeError) as exception_info:

        @simple_app.action()
        def action_with_bad_params_type(params: SomeClass):
            pass

    assert "Proper params type for action" in str(exception_info)


def test_action_decoration_passing_params_type_as_hint(simple_app):
    @simple_app.action()
    def foo(params: SampleActionParams, client: SOARClient) -> ActionOutput:
        assert True

    foo(SampleActionParams())


def test_action_decoration_passing_params_type_as_argument(simple_app):
    @simple_app.action(params_class=SampleActionParams)
    def foo(params, client: SOARClient) -> ActionOutput:
        assert True

    foo(SampleActionParams())


def test_action_run_fails_with_wrong_params_type_passed(simple_app):
    @simple_app.action()
    def action_example(params: Params, client: SOARClient) -> ActionOutput:
        pass

    with pytest.raises(TypeError) as exception_info:
        action_example("")

    assert "Provided params are not inheriting from Params" in str(exception_info)


def test_action_call_with_params(simple_app, sample_params):
    @simple_app.action()
    def action_function(params: SampleParams, client: SOARClient) -> ActionOutput:
        assert params.int_value == 1
        assert params.str_value == "test"
        assert params.pass_value == "<PASSWORD>"
        assert params.bool_value
        client.debug("TAG", "Progress was made")

    client_mock = mock.Mock()
    client_mock.debug = mock.Mock()

    action_function(sample_params, client=client_mock)

    assert client_mock.debug.call_count == 1


def test_action_call_with_params_dict(simple_app, sample_params):
    @simple_app.action()
    def action_function(params: SampleParams, client: SOARClient) -> ActionOutput:
        assert params.int_value == 1
        assert params.str_value == "test"
        assert params.pass_value == "<PASSWORD>"
        assert params.bool_value
        client.debug("TAG", "Progress was made")

    client_mock = mock.Mock()
    client_mock.debug = mock.Mock()

    action_function(sample_params, client=client_mock)

    assert client_mock.debug.call_count == 1


def test_app_action_simple_declaration(simple_app):
    @simple_app.action()
    def some_handler(params: Params) -> ActionOutput: ...

    assert len(simple_app.actions_provider.get_actions()) == 1
    assert "some_handler" in simple_app.actions_provider.get_actions()


def test_action_decoration_with_meta(simple_app):
    @simple_app.action(name="Test Function", identifier="test_function_id")
    def foo(params: Params) -> ActionOutput:
        """
        This action does nothing for now.
        """
        pass

    assert sorted(foo.meta.dict().keys()) == sorted(
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

    assert foo.meta.action == "Test Function"
    assert foo.meta.description == "This action does nothing for now."
    assert simple_app.actions_provider.get_action("test_function_id") == foo


def test_action_decoration_uses_function_name_for_action_name(simple_app):
    @simple_app.action()
    def action_function(params: Params) -> ActionOutput:
        pass

    assert action_function.meta.action == "action function"


def test_action_decoration_uses_meta_identifier_for_action_name(simple_app):
    @simple_app.action(identifier="some_identifier")
    def action_function(params: Params) -> ActionOutput:
        pass

    assert action_function.meta.action == "some identifier"


def test_action_with_mocked_client(simple_app, sample_params):
    @simple_app.action()
    def action_function(params: SampleParams, client: SOARClient) -> ActionOutput:
        client.save_progress("Progress was made")

    client_mock = mock.Mock()
    client_mock.save_progress = mock.Mock()

    action_function(sample_params, client=client_mock)

    assert client_mock.save_progress.call_count == 1


def test_action_decoration_fails_without_return_type(simple_app):
    with pytest.raises(TypeError) as exception_info:

        @simple_app.action()
        def action_function(params: Params, client: SOARClient):
            pass

    assert (
        "Action function must specify a return type via type hint or output_class parameter"
        in str(exception_info)
    )


def test_action_decoration_fails_with_return_type_not_inheriting_from_ActionOutput(
    simple_app,
):
    class SomeClass:
        pass

    with pytest.raises(TypeError) as exception_info:

        @simple_app.action()
        def action_function(params: Params, client: SOARClient) -> SomeClass:
            pass

    assert (
        "Return type for action function must be derived from ActionOutput class."
        in str(exception_info)
    )


def test_action_decoration_passing_output_type_as_hint(simple_app):
    @simple_app.action()
    def foo(params: SampleActionParams, client: SOARClient) -> SampleOutput:
        assert True

    foo(SampleActionParams())


def test_action_decoration_passing_output_type_as_argument(simple_app):
    @simple_app.action(output_class=SampleOutput)
    def foo(params: SampleActionParams, client: SOARClient):
        assert True

    foo(SampleActionParams())
