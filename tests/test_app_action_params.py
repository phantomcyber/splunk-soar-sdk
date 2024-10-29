from unittest import mock

from soar_sdk.app import App
from soar_sdk.params import Params
from tests.stubs import SampleActionParams


def test_app_action_run_use_empty_params_definition(example_app: App):

    @example_app.action()
    def foo(params: Params):
        assert True

    foo(Params())


def test_app_action_run_use_params_model(example_app):
    @example_app.action()
    def foo(params: SampleActionParams):
        assert params.field1 == 5

    foo(SampleActionParams(field1=5))


def test_app_action_handling_simple_params_conversion(example_app):

    @example_app.action()
    def foo(params: SampleActionParams):
        assert params.field1 == 5

    with mock.patch.object(
        example_app.manager.soar_client, "get_action_identifier", return_value="foo"
    ):
        example_app.manager.soar_client.handle_action({"field1": 5})


def test_app_action_handling_validation_error_raised(example_app):

    @example_app.action(params_klass=SampleActionParams)
    def foo(params: SampleActionParams):
        assert params.field1 == 5

    with mock.patch.object(
        example_app.manager.soar_client, "get_action_identifier", return_value="foo"
    ):
        success, msg = example_app.manager.soar_client.handle_action({"field1": "five"})

    assert not success
