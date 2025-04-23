from soar_sdk.cli.manifests.serializers import ParamsSerializer, OutputsSerializer
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField

import pytest


def test_params_get_sorted_fields_keys_sorts_by_field_order_value():
    class SampleParams(Params):
        d: str
        m: str
        z: str

    assert ParamsSerializer.get_sorted_fields_keys(SampleParams) == ["d", "m", "z"]


def test_params_serialize_invalid_field_raises():
    class SampleParams(Params):
        a: bytes

    with pytest.raises(TypeError) as e:
        ParamsSerializer.serialize_fields_info(SampleParams)

    e.match("Failed to serialize action parameter a: Unsupported field type: bytes")


def test_params_serialize_fields_info():
    class SampleParams(Params):
        name: str = Param(
            description="Username",
            cef_types=["user name"],
            primary=True,
        )
        event_id: int = Param(
            description="Some id of the event",
            cef_types=["event id"],
        )
        event_description: str
        event_tags: str = Param(allow_list=True, required=False)
        send_notifications: bool = Param(default=True)
        platform: str = Param(value_list=["windows", "linux", "mac"])
        api_key: str = Param(sensitive=True)

    serialized_params = ParamsSerializer.serialize_fields_info(SampleParams)

    expected_params = {
        "name": {
            "name": "name",
            "description": "Username",
            "data_type": "string",
            "contains": ["user name"],
            "required": True,
            "primary": True,
            "allow_list": False,
            "order": 0,
        },
        "event_id": {
            "name": "event_id",
            "description": "Some id of the event",
            "data_type": "numeric",
            "contains": ["event id"],
            "required": True,
            "primary": False,
            "allow_list": False,
            "order": 1,
        },
        "event_description": {
            "name": "event_description",
            "description": "Event Description",
            "data_type": "string",
            "required": True,
            "primary": False,
            "allow_list": False,
            "order": 2,
        },
        "event_tags": {
            "name": "event_tags",
            "description": "Event Tags",
            "data_type": "string",
            "required": False,
            "primary": False,
            "allow_list": True,
            "order": 3,
        },
        "send_notifications": {
            "name": "send_notifications",
            "description": "Send Notifications",
            "data_type": "boolean",
            "default": True,
            "required": True,
            "primary": False,
            "allow_list": False,
            "order": 4,
        },
        "platform": {
            "name": "platform",
            "description": "Platform",
            "data_type": "string",
            "required": True,
            "primary": False,
            "allow_list": False,
            "value_list": ["windows", "linux", "mac"],
            "order": 5,
        },
        "api_key": {
            "name": "api_key",
            "description": "Api Key",
            "data_type": "password",
            "required": True,
            "primary": False,
            "allow_list": False,
            "order": 6,
        },
    }

    assert serialized_params == expected_params


def test_outputs_serialize_with_defaults():
    serialized_outputs = OutputsSerializer.serialize_datapaths(Params, ActionOutput)
    assert serialized_outputs == [
        {
            "data_path": "action_result.status",
            "data_type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "data_type": "string",
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
            "data_type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "data_type": "string",
        },
        {
            "data_path": "action_result.data.*.string_value",
            "data_type": "string",
        },
        {
            "data_path": "action_result.data.*.int_value",
            "data_type": "numeric",
        },
        {
            "data_path": "action_result.data.*.list_value.*",
            "data_type": "string",
        },
        {
            "data_path": "action_result.data.*.cef_value",
            "data_type": "string",
            "contains": ["ip"],
            "example_values": ["1.1.1.1"],
        },
        {
            "data_path": "action_result.data.*.nested_value.bool_value",
            "data_type": "boolean",
        },
    ]


def test_outputs_serialize_with_parameters_class():
    class SampleParams(Params):
        int_value: int
        str_value: str
        bool_value: bool
        cef_value: str = Param(cef_types=["user name"])

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
            "data_type": "string",
            "example_values": ["success", "failure"],
        },
        {
            "data_path": "action_result.message",
            "data_type": "string",
        },
        {
            "data_path": "action_result.parameter.int_value",
            "data_type": "numeric",
        },
        {
            "data_path": "action_result.parameter.str_value",
            "data_type": "string",
        },
        {
            "data_path": "action_result.parameter.bool_value",
            "data_type": "boolean",
        },
        {
            "data_path": "action_result.parameter.cef_value",
            "data_type": "string",
            "contains": ["user name"],
        },
        {
            "data_path": "action_result.data.*.string_value",
            "data_type": "string",
        },
        {
            "data_path": "action_result.data.*.int_value",
            "data_type": "numeric",
        },
        {
            "data_path": "action_result.data.*.list_value.*",
            "data_type": "string",
        },
        {
            "data_path": "action_result.data.*.cef_value",
            "data_type": "string",
            "contains": ["ip"],
            "example_values": ["1.1.1.1"],
        },
        {
            "data_path": "action_result.data.*.nested_value.bool_value",
            "data_type": "boolean",
        },
    ]
