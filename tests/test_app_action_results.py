from unittest import mock

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from tests.mocks.dynamic_mocks import ArgReturnMock
from tests.stubs import SampleActionParams


def test_app_action_called_with_legacy_result_set_returns_this_result(
    simple_app, simple_action_input
):
    action_result = ActionResult(True, "Action succeeded")
    client_mock = mock.Mock()
    client_mock.add_result = mock.Mock(return_value=action_result)

    @simple_app.action()
    def action_returning_action_result(params: SampleActionParams, client: SOARClient):
        return action_result

    result = action_returning_action_result(
        SampleActionParams(field1=5), client=client_mock
    )

    assert result is True
    assert client_mock.add_result.call_count == 1
    client_mock.add_result.assert_called_with(action_result)


def test_app_action_called_with_tuple_creates_the_result(
    simple_app, simple_action_input
):
    client_mock = mock.Mock()
    client_mock.add_result = ArgReturnMock()

    @simple_app.action()
    def action_returning_tuple(params: SampleActionParams, client: SOARClient):
        return True, "Action succeeded"

    result = action_returning_tuple(SampleActionParams(field1=5), client=client_mock)

    assert result is True
    assert client_mock.add_result.call_count == 1
