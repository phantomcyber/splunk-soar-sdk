from soar_sdk.cli.manifests.serializers import ParamsSerializer, OutputsSerializer
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField


def test_params_get_sorted_fields_keys_sorts_by_field_order_value():
    class SampleParams(Params):
        z: str = Param(2, "z param")
        d: str = Param(0, "d param")
        m: str = Param(1, "m param")

    assert ParamsSerializer.get_sorted_fields_keys(SampleParams) == ["d", "m", "z"]


def test_params_field_serialize_with_defaults():
    class SomeParams(Params):
        the_param: str = Param(0, "the_param param")

    assert ParamsSerializer.serialize_field_info(
        SomeParams.__fields__.get("the_param")
    ) == {
        "name": "the_param",
        "description": "the_param param",
        "data_type": "string",
        "contains": [],
        "required": True,
        "primary": True,
        "values_list": [],
        "allow_list": False,
        "default": "",
        "order": 0,
    }


def test_params_serialize_fields_info():
    class SampleParams(Params):
        name: str = Param(
            description="Some Description",  # required, starting with capital
            data_type="string",
            contains=["user name"],
            required=True,
            primary=True,
            values_list=[],
            default="",
            order=0,
            allow_list=False,
        )
        event_id: int = Param(
            description="Some id of the event",
            data_type="string",
            contains=["event id"],
            required=True,
            primary=True,
            values_list=[],
            default="",
            order=1,
            allow_list=False,
        )

    serialized_params = ParamsSerializer.serialize_fields_info(SampleParams)

    expected_params = {
        "name": {
            "name": "name",
            "description": "Some Description",
            "data_type": "string",
            "contains": ["user name"],
            "required": True,
            "primary": True,
            "values_list": [],
            "allow_list": False,
            "default": "",
            "order": 0,
        },
        "event_id": {
            "name": "event_id",
            "description": "Some id of the event",
            "data_type": "string",
            "contains": ["event id"],
            "required": True,
            "primary": True,
            "values_list": [],
            "allow_list": False,
            "default": "",
            "order": 1,
        },
    }

    for param in serialized_params:
        assert serialized_params[param] == expected_params[param]


def test_outputs_serialize_with_defaults():
    serialized_outputs = OutputsSerializer.serialize_datapaths(Params, ActionOutput)
    assert serialized_outputs == [
        {
            "data_path": "action_result.status",
            "type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "type": "string",
        },
    ]


def test_outputs_serialize_output_class():
    class SampleNestedOutput(ActionOutput):
        bool_value: bool

    class SampleOutput(ActionOutput):
        string_value: str
        int_value: int
        list_value: list[str]
        cef_value: str = OutputField(cef_types=["ip"], example_values=["1.1.1.1"])
        nested_value: SampleNestedOutput

    serialized_outputs = OutputsSerializer.serialize_datapaths(Params, SampleOutput)

    assert serialized_outputs == [
        {
            "data_path": "action_result.status",
            "type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "type": "string",
        },
        {
            "data_path": "action_result.data.*.string_value",
            "type": "string",
        },
        {
            "data_path": "action_result.data.*.int_value",
            "type": "numeric",
        },
        {
            "data_path": "action_result.data.*.list_value.*",
            "type": "string",
        },
        {
            "data_path": "action_result.data.*.cef_value",
            "type": "string",
            "contains": ["ip"],
            "example_values": ["1.1.1.1"],
        },
        {
            "data_path": "action_result.data.*.nested_value.bool_value",
            "type": "boolean",
        },
    ]


def test_outputs_serialize_with_parameters_class():
    class SampleParams(Params):
        int_value: int = Param(0, "Integer Value", data_type="numeric")
        str_value: str = Param(1, "String Value")
        bool_value: bool = Param(2, "Boolean Value", data_type="boolean")

    class SampleNestedOutput(ActionOutput):
        bool_value: bool

    class SampleOutput(ActionOutput):
        string_value: str
        int_value: int
        list_value: list[str]
        cef_value: str = OutputField(cef_types=["ip"], example_values=["1.1.1.1"])
        nested_value: SampleNestedOutput

    serialized_outputs = OutputsSerializer.serialize_datapaths(
        SampleParams, SampleOutput
    )

    assert serialized_outputs == [
        {
            "data_path": "action_result.status",
            "type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "type": "string",
        },
        {
            "data_path": "action_result.parameter.int_value",
            "type": "numeric",
        },
        {
            "data_path": "action_result.parameter.str_value",
            "type": "string",
        },
        {
            "data_path": "action_result.parameter.bool_value",
            "type": "boolean",
        },
        {
            "data_path": "action_result.data.*.string_value",
            "type": "string",
        },
        {
            "data_path": "action_result.data.*.int_value",
            "type": "numeric",
        },
        {
            "data_path": "action_result.data.*.list_value.*",
            "type": "string",
        },
        {
            "data_path": "action_result.data.*.cef_value",
            "type": "string",
            "contains": ["ip"],
            "example_values": ["1.1.1.1"],
        },
        {
            "data_path": "action_result.data.*.nested_value.bool_value",
            "type": "boolean",
        },
    ]
