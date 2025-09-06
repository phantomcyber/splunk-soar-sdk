from unittest import mock

import pytest

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput
from tests.stubs import SampleActionParams, SampleNestedOutput, SampleOutput
from soar_sdk.exceptions import ActionFailure, ActionRegistrationError
from tests.mocks.importable_action import importable_action, importable_view_handler
import httpx


class SampleParams(Params):
    int_value: int = Param(description="Integer Value")
    str_value: str = Param(description="String Value")
    pass_value: str = Param(description="Password Value", sensitive=True)
    bool_value: bool = Param(description="Boolean Value")


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
    with pytest.raises(TypeError, match=r".*must accept at least"):

        @simple_app.action()
        def action_function_no_params() -> ActionOutput:
            pass


def test_action_decoration_fails_without_params_type_set(simple_app):
    with pytest.raises(TypeError, match=r".*no params type set"):

        @simple_app.action()
        def action_function_no_params_type(params) -> ActionOutput:
            pass


def test_action_decoration_fails_with_params_not_inheriting_from_Params(simple_app):
    class SomeClass:
        pass

    with pytest.raises(TypeError, match=r".*Proper params type for action"):

        @simple_app.action()
        def action_with_bad_params_type(params: SomeClass):
            pass


def test_action_decoration_passing_params_type_as_hint(simple_app):
    @simple_app.action()
    def foo(params: SampleActionParams, soar: SOARClient) -> ActionOutput:
        assert True

    foo(SampleActionParams())


def test_action_decoration_passing_params_type_as_argument(simple_app):
    @simple_app.action(params_class=SampleActionParams)
    def foo(params, soar: SOARClient) -> ActionOutput:
        assert True

    foo(SampleActionParams())


def test_action_run_fails_with_wrong_params_type_passed(simple_app):
    @simple_app.action()
    def action_example(params: Params, soar: SOARClient) -> ActionOutput:
        pass

    with pytest.raises(TypeError, match=r".*not inheriting from Params"):
        action_example("")


def test_action_call_with_params(simple_app: App, sample_params: SampleParams):
    @simple_app.action()
    def action_function(params: SampleParams, soar: SOARClient) -> ActionOutput:
        assert params.int_value == 1
        assert params.str_value == "test"
        assert params.pass_value == "<PASSWORD>"
        assert params.bool_value

    client_mock = mock.Mock(spec=SOARClient)
    action_function(sample_params, soar=client_mock)


def test_action_call_with_params_dict(simple_app, sample_params):
    @simple_app.action()
    def action_function(params: SampleParams, soar: SOARClient) -> ActionOutput:
        assert params.int_value == 1
        assert params.str_value == "test"
        assert params.pass_value == "<PASSWORD>"
        assert params.bool_value

    client_mock = mock.Mock()

    action_function(sample_params, soar=client_mock)


def test_action_call_with_state(simple_app, sample_params):
    initial_state = {"key": "initial"}
    updated_state = {"key": "updated"}

    @simple_app.action()
    def action_function(params: SampleParams, soar: SOARClient) -> ActionOutput:
        assert soar.ingestion_state == initial_state
        assert soar.auth_state == initial_state
        assert soar.asset_cache == initial_state

        soar.ingestion_state = updated_state
        soar.auth_state = updated_state
        soar.asset_cache = updated_state

    client_mock = mock.Mock()

    client_mock.ingestion_state = initial_state
    client_mock.auth_state = initial_state
    client_mock.asset_cache = initial_state

    action_function(sample_params, soar=client_mock)

    assert client_mock.ingestion_state == updated_state
    assert client_mock.auth_state == updated_state
    assert client_mock.asset_cache == updated_state


def test_app_action_simple_declaration(simple_app: App):
    @simple_app.action()
    def some_handler(params: Params) -> ActionOutput: ...

    assert len(simple_app.actions_manager.get_actions()) == 1
    assert "some_handler" in simple_app.actions_manager.get_actions()


def test_action_decoration_with_meta(simple_app: App):
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
    assert simple_app.actions_manager.get_action("test_function_id") == foo


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
    def action_function(params: SampleParams, soar: SOARClient) -> ActionOutput:
        soar.save_progress("Progress was made")

    client_mock = mock.Mock()
    client_mock.save_progress = mock.Mock()

    action_function(sample_params, soar=client_mock)

    assert client_mock.save_progress.call_count == 1


def test_action_decoration_fails_without_return_type(simple_app):
    with pytest.raises(TypeError, match=r".*must specify.*return type"):

        @simple_app.action()
        def action_function(params: Params, soar: SOARClient):
            pass


def test_action_decoration_fails_with_return_type_not_inheriting_from_ActionOutput(
    simple_app,
):
    class SomeClass:
        pass

    with pytest.raises(TypeError, match=r".*Return type.*must be derived"):

        @simple_app.action()
        def action_function(params: Params, soar: SOARClient) -> SomeClass:
            pass


def test_action_cannot_be_test_connectivity(simple_app):
    with pytest.raises(TypeError, match=r".*test_connectivity.*reserved"):

        @simple_app.action()
        def test_connectivity(params: Params, soar: SOARClient) -> ActionOutput:
            pass


def test_action_names_must_be_unique(simple_app: App):
    @simple_app.action(identifier="test_function_id")
    def action_test(params: Params) -> ActionOutput:
        pass

    with pytest.raises(TypeError, match=r".*already used"):

        @simple_app.action(identifier="test_function_id")
        def other_action_test(params: Params) -> ActionOutput:
            pass


def test_action_decoration_passing_output_type_as_hint(simple_app):
    @simple_app.action()
    def foo(params: SampleActionParams, soar: SOARClient) -> SampleOutput:
        assert True

    foo(SampleActionParams())


def test_action_decoration_passing_output_type_as_argument(simple_app):
    @simple_app.action(output_class=SampleOutput)
    def foo(params: SampleActionParams, soar: SOARClient):
        assert True

    foo(SampleActionParams())


def test_action_failure_raised(simple_app: App):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        raise ActionFailure("Action failed")

    # Mock the add_result method
    simple_app.actions_manager.add_result = mock.Mock()

    result = action_function(Params(), soar=simple_app.soar_client)
    assert not result
    assert simple_app.actions_manager.add_result.call_count == 1


def test_other_failure_raised(simple_app: App):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        raise ValueError("Value error occurred")

    result = action_function(Params(), soar=simple_app.soar_client)

    assert not result


def test_client_get(simple_app: App, mock_get_any_soar_call):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        soar.get("rest/version")
        return ActionOutput()

    result = action_function(Params(), soar=simple_app.soar_client)
    assert result
    assert mock_get_any_soar_call.called


def test_client_post(simple_app: App, mock_post_any_soar_call):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        soar.post("rest/version")
        assert result
        return ActionOutput()

    result = action_function(Params(), soar=simple_app.soar_client)
    assert mock_post_any_soar_call.called


def test_client_put(simple_app: App, mock_put_any_call):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        soar.put("rest/version")
        assert result
        return ActionOutput()

    result = action_function(Params(), soar=simple_app.soar_client)
    assert mock_put_any_call.called


def test_delete(
    simple_app: App,
    mock_delete_any_soar_call,
):
    class TestClient(SOARClient):
        @property
        def client(self):
            return httpx.Client(base_url="https://example.com", verify=False)

        def update_client(self, soar_auth, asset_id):
            pass

    @simple_app.action()
    def delete_action(params: Params, soar: SOARClient) -> ActionOutput:
        soar.delete("/some/delete/endpoint")
        assert result
        assert ActionOutput()

    result = delete_action(SampleParams(), soar=TestClient())
    assert mock_delete_any_soar_call.call_count == 1


def test_direct_action_registration(simple_app: App):
    from tests.mocks.importable_action import importable_action

    simple_app.register_action(
        importable_action,
        identifier="register_direct_callable",
    )


def test_register_action_basic(simple_app: App):
    registered_action = simple_app.register_action(
        importable_action,
        name="Importable Action",
        identifier="importable_action",
        description="An importable action for testing",
        verbose="This is a verbose description",
        action_type="investigate",
    )

    # Verify the action was registered
    assert registered_action is not None
    assert hasattr(registered_action, "meta")
    assert registered_action.meta.action == "Importable Action"
    assert registered_action.meta.identifier == "importable_action"
    assert registered_action.meta.description == "An importable action for testing"
    assert registered_action.meta.verbose == "This is a verbose description"
    assert registered_action.meta.type == "investigate"

    # Verify the action is in the app's actions
    actions = simple_app.get_actions()
    assert "importable_action" in actions
    assert actions["importable_action"] == registered_action


def test_register_action_with_view_handler(simple_app: App):
    import inspect
    import sys
    import types

    original_signature = inspect.signature(importable_view_handler)
    assert len(original_signature.parameters) == 1

    module_name = importable_view_handler.__module__
    assert module_name in sys.modules

    # Register the importable action with view handler
    registered_action = simple_app.register_action(
        importable_action,
        name="Importable Action with View",
        view_handler=importable_view_handler,
        view_template="sample_template.html",
    )

    # Verify the action was registered with view handler
    assert registered_action.meta.view_handler is not None
    module = sys.modules[module_name]
    replaced_function = getattr(module, importable_view_handler.__name__)

    assert replaced_function is not importable_view_handler

    # The @wraps decorator preserves the original signature for inspect.signature()
    # but the actual callable code should have the wrapper signature
    if isinstance(replaced_function, types.FunctionType):
        code_args = replaced_function.__code__.co_varnames[
            : replaced_function.__code__.co_argcount
        ]
        assert code_args == ("action", "all_app_runs", "context")
        assert replaced_function.__code__.co_argcount == 3

    # Additional verification: the action should be properly registered
    actions = simple_app.get_actions()
    assert "importable_action" in actions


def test_register_action_with_view_handler_empty_module(simple_app: App):
    importable_view_handler.__module__ = ""

    registered_action = simple_app.register_action(
        importable_action,
        name="Importable Action with Empty Module View",
        view_handler=importable_view_handler,
        view_template="sample_template.html",
    )

    assert registered_action.meta.view_handler is not None


def test_register_action_with_view_handler_module_not_in_sys_modules(simple_app: App):
    # Create a view handler with a fake module name
    def fake_module_view_handler(output: list[ActionOutput]) -> dict:
        return {"data": "test"}

    fake_module_view_handler.__module__ = "nonexistent.fake.module"

    with pytest.raises(ActionRegistrationError):
        simple_app.register_action(
            importable_action,
            name="Importable Action with Fake Module View",
            view_handler=fake_module_view_handler,
            view_template="sample_template.html",
        )
