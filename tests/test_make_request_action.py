import pytest
import pytest_mock
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import MakeRequestOutput, OutputField
from soar_sdk.app import App
from soar_sdk.params import MakeRequestParams, Params
from soar_sdk.exceptions import ActionFailure
from soar_sdk.asset import BaseAsset


class ValidAsset(BaseAsset):
    normal_field: str
    another_field: int


def test_make_request_action_decoration_fails_when_used_more_than_once(
    app_with_action: App,
):
    @app_with_action.make_request()
    def http_action(params: MakeRequestParams) -> MakeRequestOutput:
        pass

    with pytest.raises(TypeError) as exception_info:

        @app_with_action.make_request()
        def http_action2(params: MakeRequestParams) -> MakeRequestOutput:
            pass

    assert (
        "The 'make_request' decorator can only be used once per App instance."
        in str(exception_info)
    )


def test_make_request_action_decoration(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    @app_with_action.make_request()
    def http_action(params: MakeRequestParams) -> MakeRequestOutput:
        """
        This action does nothing for now.
        """
        return MakeRequestOutput(
            status_code=200,
            response_body="Hello, world!",
        )

    manager_mock = mocker.patch.object(
        app_with_action, "actions_manager", autospec=True
    )
    result = http_action(params=MakeRequestParams(http_method="GET", endpoint="/"))
    assert result
    assert manager_mock.add_result.call_count == 1


def test_make_request_action_without_make_request_params(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.make_request()
        def http_action(soar: SOARClient) -> MakeRequestOutput:
            pass

    assert (
        "Make request action function must have at least one parameter of type MakeRequestParams, got <class 'soar_sdk.abstract.SOARClient'>"
        in str(exception_info)
    )

    with pytest.raises(TypeError) as exception_info:

        @app_with_action.make_request()
        def http_action(params: Params, soar: SOARClient) -> MakeRequestOutput:
            pass

    assert (
        "Make request action function must have at least one parameter of type MakeRequestParams, got <class 'soar_sdk.params.Params'>"
        in str(exception_info)
    )


def test_invalid_output_type(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.make_request()
        def http_action(params: MakeRequestParams) -> str:
            pass

    assert (
        "Return type for action function must be either MakeRequestOutput or derived from ActionOutput or MakeRequestOutput class."
        in str(exception_info)
    )


def test_make_request_action_output_class(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    class CustomMakeRequestOutput(MakeRequestOutput):
        error: str = OutputField(example_values=["Invalid credentials"])

    @app_with_action.make_request(output_class=CustomMakeRequestOutput)
    def http_action(params: MakeRequestParams, asset: ValidAsset):
        return CustomMakeRequestOutput(
            status_code=401,
            response_body="Invalid credentials",
            error="Invalid credentials",
        )

    manager_mock = mocker.patch.object(
        app_with_action, "actions_manager", autospec=True
    )
    result = http_action(
        params=MakeRequestParams(http_method="GET", endpoint="/"),
        asset=ValidAsset(normal_field="test", another_field=42),
    )
    assert result
    assert manager_mock.add_result.call_count == 1


def test_no_output_class(app_with_action: App):
    with pytest.raises(TypeError) as exception_info:

        @app_with_action.make_request()
        def http_action(params: MakeRequestParams):
            pass

    assert (
        "Action function must specify a return type via type hint or output_class parameter"
        in str(exception_info)
    )


def test_parameter_validation_error(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that parameter validation errors are handled properly (lines 93-95)"""

    @app_with_action.make_request()
    def http_action(params: MakeRequestParams) -> MakeRequestOutput:
        return MakeRequestOutput(status_code=200, response_body="OK")

    manager_mock = mocker.patch.object(
        app_with_action, "actions_manager", autospec=True
    )

    invalid_params = "invalid"

    result = http_action(params=invalid_params)

    assert result is False
    assert manager_mock.add_result.call_count == 1


def test_make_request_action_raises_exception_propagates(app_with_action: App):
    """Test that exceptions raised in the make request action function are handled and return False."""

    @app_with_action.make_request()
    def http_action(params: MakeRequestParams) -> MakeRequestOutput:
        raise ValueError("error")
        return MakeRequestOutput(status_code=200, response_body="OK")

    result = http_action(params=MakeRequestParams(http_method="GET", endpoint="/"))
    assert result is False


def test_make_request_action_raises_action_failure_propagates(app_with_action: App):
    @app_with_action.make_request()
    def http_action(params: MakeRequestParams, asset: ValidAsset) -> MakeRequestOutput:
        raise ActionFailure("error")

    result = http_action(
        params=MakeRequestParams(http_method="GET", endpoint="/"),
        asset=ValidAsset(normal_field="test", another_field=42),
    )
    assert result is False
