import pytest
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import GenericActionOutput, OutputField
from unittest import mock
from soar_sdk.app import App
from soar_sdk.params import GenericActionParams, Params
from soar_sdk.exceptions import ActionFailure
from soar_sdk.asset import BaseAsset


class ValidAsset(BaseAsset):
    normal_field: str
    another_field: int


def test_generic_action_decoration_fails_when_used_more_than_once(app_with_action: App):
    @app_with_action.generic_action()
    def http_action(params: GenericActionParams) -> GenericActionOutput:
        pass

    with pytest.raises(TypeError) as exception_info:

        @app_with_action.generic_action()
        def http_action2(params: GenericActionParams) -> GenericActionOutput:
            pass

    assert (
        "The 'generic_action' decorator can only be used once per App instance."
        in str(exception_info)
    )


def test_generic_action_decoration(app_with_action: App):
    @app_with_action.generic_action()
    def http_action(params: GenericActionParams) -> GenericActionOutput:
        """
        This action does nothing for now.
        """
        return GenericActionOutput(
            status_code=200,
            response_body="Hello, world!",
        )

    app_with_action.actions_manager = mock.Mock()
    result = http_action(params=GenericActionParams(http_method="GET", endpoint="/"))
    assert result
    assert app_with_action.actions_manager.add_result.call_count == 1


def test_generic_action_without_generic_action_params(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.generic_action()
        def http_action(soar: SOARClient) -> GenericActionOutput:
            pass

    assert (
        "Generic action function must have at least one parameter of type GenericActionParams, got <class 'soar_sdk.abstract.SOARClient'>"
        in str(exception_info)
    )

    with pytest.raises(TypeError) as exception_info:

        @app_with_action.generic_action()
        def http_action(params: Params, soar: SOARClient) -> GenericActionOutput:
            pass

    assert (
        "Generic action function must have at least one parameter of type GenericActionParams, got <class 'soar_sdk.params.Params'>"
        in str(exception_info)
    )


def test_invalid_output_type(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.generic_action()
        def http_action(params: GenericActionParams) -> str:
            pass

    assert (
        "Return type for action function must be either GenericActionOutput or derived from ActionOutput or GenericActionOutput class."
        in str(exception_info)
    )


def test_generic_action_output_class(app_with_action: App):
    class CustomGenericActionOutput(GenericActionOutput):
        error: str = OutputField(example_values=["Invalid credentials"])

    @app_with_action.generic_action(output_class=CustomGenericActionOutput)
    def http_action(params: GenericActionParams, asset: ValidAsset):
        return CustomGenericActionOutput(
            status_code=401,
            response_body="Invalid credentials",
            error="Invalid credentials",
        )

    app_with_action.actions_manager = mock.Mock()
    result = http_action(
        params=GenericActionParams(http_method="GET", endpoint="/"),
        asset=ValidAsset(normal_field="test", another_field=42),
    )
    assert result
    assert app_with_action.actions_manager.add_result.call_count == 1


def test_no_output_class(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.generic_action()
        def http_action(params: GenericActionParams):
            pass

    assert (
        "Action function must specify a return type via type hint or output_class parameter"
        in str(exception_info)
    )


def test_parameter_validation_error(app_with_action: App):
    """Test that parameter validation errors are handled properly (lines 93-95)"""

    @app_with_action.generic_action()
    def http_action(params: GenericActionParams) -> GenericActionOutput:
        return GenericActionOutput(status_code=200, response_body="OK")

    app_with_action.actions_manager = mock.Mock()

    invalid_params = "invalid"

    result = http_action(params=invalid_params)

    assert result is False
    assert app_with_action.actions_manager.add_result.call_count == 1


def test_generic_action_raises_exception_propagates(app_with_action: App):
    """Test that exceptions raised in the generic action function are handled and return False."""

    @app_with_action.generic_action()
    def http_action(params: GenericActionParams, client=None) -> GenericActionOutput:
        raise ValueError("error")
        return GenericActionOutput(status_code=200, response_body="OK")

    client_mock = mock.Mock()

    result = http_action(
        params=GenericActionParams(http_method="GET", endpoint="/"), client=client_mock
    )
    assert result is False


def test_generic_action_raises_action_failure_propagates(app_with_action: App):
    @app_with_action.generic_action()
    def http_action(
        params: GenericActionParams, asset: ValidAsset
    ) -> GenericActionOutput:
        raise ActionFailure("error")

    result = http_action(
        params=GenericActionParams(http_method="GET", endpoint="/"),
        asset=ValidAsset(normal_field="test", another_field=42),
    )
    assert result is False
