import pytest
from unittest import mock
from pydantic import BaseModel

from soar_sdk.views.view_parser import ViewFunctionParser
from soar_sdk.action_results import ActionOutput
from soar_sdk.models.view import ViewContext


class SampleViewOutput(ActionOutput):
    name: str
    value: int


class SampleComponentData(BaseModel):
    title: str
    count: int


def test_view_function_parser_auto_detect_output_class_from_list_annotation():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)
    assert parser.output_class == SampleViewOutput


def test_view_function_parser_auto_detect_output_class_fails_no_annotation():
    def test_function(outputs):
        pass

    with pytest.raises(TypeError, match="Could not auto-detect ActionOutput class"):
        ViewFunctionParser(test_function)


def test_view_function_parser_parse_action_results_success():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    app_run_metadata = {"total_objects": 1, "total_objects_successful": 1}
    raw_all_app_runs = [(app_run_metadata, [mock_result])]

    parsed_outputs = parser.parse_action_results(raw_all_app_runs)

    assert len(parsed_outputs) == 1
    assert isinstance(parsed_outputs[0], SampleViewOutput)
    assert parsed_outputs[0].name == "test"
    assert parsed_outputs[0].value == 42


def test_view_function_parser_parse_action_results_invalid_data():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"invalid": "data"}]

    app_run_metadata = {"total_objects": 1, "total_objects_successful": 1}
    raw_all_app_runs = [(app_run_metadata, [mock_result])]

    with pytest.raises(ValueError, match="Data parsing failed for SampleViewOutput"):
        parser.parse_action_results(raw_all_app_runs)


def test_view_function_parser_execute_with_one_param():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return f"Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Found 1 outputs"


def test_view_function_parser_execute_invalid_raw_all_app_runs_type():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return "test"

    parser = ViewFunctionParser(test_function)

    action = "test_action"
    raw_all_app_runs = "invalid"
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    with pytest.raises(ValueError, match="not enough values to unpack"):
        parser.execute(action, raw_all_app_runs, raw_context)


def test_view_function_parser_auto_detect_output_class_from_direct_annotation():
    def test_function(output: SampleViewOutput):
        pass

    parser = ViewFunctionParser(test_function)
    assert parser.output_class == SampleViewOutput


def test_view_function_parser_auto_detect_output_class_invalid_type():
    def test_function(outputs: list[str]):
        pass

    with pytest.raises(TypeError, match="Could not auto-detect ActionOutput class"):
        ViewFunctionParser(test_function)


def test_view_function_parser_execute_with_two_params():
    def test_function(context: ViewContext, outputs: list[SampleViewOutput]) -> str:
        return f"Context app: {context.app}, Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Context app: 2, Found 1 outputs"


def test_view_function_parser_execute_with_three_params():
    def test_function(
        context: ViewContext, action: str, outputs: list[SampleViewOutput]
    ) -> str:
        return f"Action: {action}, Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Action: test_action, Found 1 outputs"


def test_view_function_parser_parse_action_results_non_dict_metadata():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    mock_metadata = mock.Mock()
    raw_all_app_runs = [(mock_metadata, [mock_result])]

    parsed_outputs = parser.parse_action_results(raw_all_app_runs)

    assert len(parsed_outputs) == 1


def test_view_function_parser_execute_context_parsing_fails():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return "test"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "test"
