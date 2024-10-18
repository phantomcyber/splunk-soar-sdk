from unittest import mock

import pytest
from pydantic import ValidationError

from soar_sdk.app import App
from soar_sdk.params import Param, Params


class SampleActionParams(Params):
    field1: int = Param(0, "Some description")


def test_app_action_run_use_empty_params_definition(example_app):
    @example_app.action()
    def foo(ctx: App, params: Params):
        assert True

    foo({})


def test_app_action_run_use_params_definition_from_typehints(example_app):
    @example_app.action()
    def foo(ctx: App, params: SampleActionParams):
        assert params.field1 == 5

    foo({"field1": 5})


def test_app_action_run_use_explicit_params_definition(example_app):
    @example_app.action()
    def foo(ctx: App, params: SampleActionParams):
        assert params.field1 == 5

    foo({"field1": 5})


def test_app_action_run_validates_params(example_app):
    @example_app.action(params_klass=SampleActionParams)
    def foo(ctx, params):
        assert params.field1 == 5

    with pytest.raises(ValidationError):
        foo({"field1": "five"})


def test_app_action_handling_simple_params_conversion(example_app):

    @example_app.action()
    def foo(ctx, params: SampleActionParams):
        assert params.field1 == 5

    with mock.patch.object(
        example_app.connector, "get_action_identifier", return_value="foo"
    ):
        example_app.connector._actions = example_app._actions
        example_app.connector.handle_action({"field1": 5})


def test_app_action_handling_validation_error_raised(example_app):

    @example_app.action(params_klass=SampleActionParams)
    def foo(ctx, params: SampleActionParams):
        assert params.field1 == 5

    with pytest.raises(ValidationError):
        with mock.patch.object(
            example_app.connector, "get_action_identifier", return_value="foo"
        ):
            example_app.connector._actions = example_app._actions
            example_app.connector.handle_action({"field1": "five"})
