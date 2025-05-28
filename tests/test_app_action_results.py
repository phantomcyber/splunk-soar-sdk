from unittest import mock

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from tests.mocks.dynamic_mocks import ArgReturnMock
from tests.stubs import SampleActionParams, SampleOutput, SampleNestedOutput


def test_app_action_called_with_legacy_result_set_returns_this_result(app_with_action):
    action_result = ActionOutput()
    client_mock = mock.Mock()
    client_mock.add_result = mock.Mock(return_value=action_result)

    @app_with_action.action()
    def action_returning_action_result(
        params: SampleActionParams, soar: SOARClient
    ) -> ActionOutput:
        return action_result

    result = action_returning_action_result(
        SampleActionParams(field1=5), soar=client_mock
    )

    assert result is True
    assert client_mock.add_result.call_count == 1
    assert client_mock.add_result.call_args[0][0].get_param() == {}


def test_app_action_called_with_simple_result_creates_the_result(app_with_action):
    client_mock = mock.Mock()
    client_mock.add_result = ArgReturnMock()

    @app_with_action.action()
    def action_returning_simple_result(
        params: SampleActionParams, soar: SOARClient
    ) -> ActionOutput:
        return ActionOutput()

    result = action_returning_simple_result(
        SampleActionParams(field1=5), soar=client_mock
    )

    assert result is True
    assert client_mock.add_result.call_count == 1
    assert client_mock.add_result.call_args[0][0].get_param() == {}


def test_app_action_called_with_more_complex_result_creates_the_result(app_with_action):
    client_mock = mock.Mock()
    client_mock.add_result = ArgReturnMock()

    output = SampleOutput(
        string_value="test",
        int_value=1,
        list_value=["a", "b"],
        bool_value=True,
        nested_value=SampleNestedOutput(bool_value=True),
    )

    @app_with_action.action()
    def action_returning_complex_result(
        params: SampleActionParams, soar: SOARClient
    ) -> SampleOutput:
        return output

    result = action_returning_complex_result(
        SampleActionParams(field1=5), soar=client_mock
    )
    assert result is True
    assert client_mock.add_result.call_count == 1
    assert client_mock.add_result.call_args[0][0].get_param() == {
        "string_value": "test",
        "int_value": 1,
        "list_value": ["a", "b"],
        "bool_value": True,
        "nested_value": {"bool_value": True},
    }
