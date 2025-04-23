import pytest
from soar_sdk.action_results import ActionOutput, OutputField


class ExampleInnerData(ActionOutput):
    inner_string: str = OutputField(
        example_values=["example_value_1", "example_value_2"]
    )


class ExampleActionOutput(ActionOutput):
    stringy_field: str
    list_of_strings: list[str]
    nested_lists: list[list[int]]
    cef_data: str = OutputField(
        cef_types=["ip"], example_values=["192.168.0.1", "1.1.1.1"]
    )
    nested_type: ExampleInnerData
    list_of_types: list[ExampleInnerData]


class BadActionOutput(ActionOutput):
    byte_field: bytes


def test_action_output_to_json_schema():
    expected_schema = [
        {"data_path": "action_result.data.*.stringy_field", "data_type": "string"},
        {"data_path": "action_result.data.*.list_of_strings.*", "data_type": "string"},
        {"data_path": "action_result.data.*.nested_lists.*.*", "data_type": "numeric"},
        {
            "data_path": "action_result.data.*.cef_data",
            "data_type": "string",
            "contains": ["ip"],
            "example_values": ["192.168.0.1", "1.1.1.1"],
        },
        {
            "data_path": "action_result.data.*.nested_type.inner_string",
            "data_type": "string",
            "example_values": ["example_value_1", "example_value_2"],
        },
        {
            "data_path": "action_result.data.*.list_of_types.*.inner_string",
            "data_type": "string",
            "example_values": ["example_value_1", "example_value_2"],
        },
    ]

    schema = list(ExampleActionOutput._to_json_schema())
    assert schema == expected_schema


def test_action_output_to_json_schema_bad_type():
    with pytest.raises(TypeError):
        next(BadActionOutput._to_json_schema())


def test_parse_action_output():
    raw_data = {
        "stringy_field": "example_string",
        "list_of_strings": ["string1", "string2"],
        "nested_lists": [[1, 2], [3, 4]],
        "cef_data": "42.42.42.42",
        "nested_type": {"inner_string": "inner_value"},
        "list_of_types": [
            {"inner_string": "inner_value_1"},
            {"inner_string": "inner_value_2"},
        ],
    }
    parsed_data = ExampleActionOutput.parse_obj(raw_data)
    assert parsed_data.stringy_field == "example_string"
    assert parsed_data.list_of_strings == ["string1", "string2"]
    assert parsed_data.nested_lists == [[1, 2], [3, 4]]
    assert parsed_data.cef_data == "42.42.42.42"
    assert parsed_data.nested_type.inner_string == "inner_value"
    assert len(parsed_data.list_of_types) == 2
    assert parsed_data.list_of_types[0].inner_string == "inner_value_1"
    assert parsed_data.list_of_types[1].inner_string == "inner_value_2"
