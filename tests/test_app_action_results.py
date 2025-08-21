from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.action_results import ActionOutput
from tests.mocks.dynamic_mocks import ArgReturnMock
from tests.stubs import SampleActionParams, SampleOutput, SampleNestedOutput


def test_app_action_called_with_simple_result_creates_the_result(app_with_action: App):
    actions_manager_mock = app_with_action.actions_manager
    actions_manager_mock.add_result = ArgReturnMock()

    @app_with_action.action()
    def action_returning_simple_result(
        params: SampleActionParams, soar: SOARClient
    ) -> ActionOutput:
        return ActionOutput()

    result = action_returning_simple_result(
        SampleActionParams(field1=5), soar=app_with_action.soar_client
    )

    assert result is True
    assert actions_manager_mock.add_result.call_count == 1
    assert actions_manager_mock.add_result.call_args[0][0].get_param() == {"field1": 5}


def test_app_action_called_with_more_complex_result_creates_the_result(
    app_with_action: App,
):
    actions_manager_mock = app_with_action.actions_manager
    actions_manager_mock.add_result = ArgReturnMock()

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
        SampleActionParams(field1=5), soar=app_with_action.soar_client
    )
    assert result is True
    assert actions_manager_mock.add_result.call_count == 1
    assert actions_manager_mock.add_result.call_args[0][0].get_data() == [
        {
            "string_value": "test",
            "int_value": 1,
            "list_value": ["a", "b"],
            "bool_value": True,
            "nested_value": {"bool_value": True},
        }
    ]
