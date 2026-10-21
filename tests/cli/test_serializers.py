from typing import Annotated

import pytest
from pydantic import Field

from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.cli.manifests.serializers import OutputsSerializer, ParamsSerializer
from soar_sdk.params import Param, Params


def test_output_schema_uses_type_arrays_for_nullable_fields():
    class NullableParams(Params):
        name: str | None = Param(required=False)

    class NullableOutput(ActionOutput):
        email: str | None = OutputField(
            cef_types=["email"], example_values=["person@example.com"]
        )
        count: int | None = Field(
            default=None, json_schema_extra={"column_name": "Count", "column_order": 0}
        )
        ratio: float | None = None
        enabled: bool | None = None
        values: list[str | None]
        required_nullable: str | None

    class NullableSummary(ActionOutput):
        count: int | None = None

    schema = OutputsSerializer.serialize_output_schema(
        NullableParams, NullableOutput, NullableSummary
    )
    fields = schema["$defs"]["NullableOutput"]["properties"]

    assert fields["email"]["type"] == ["string", "null"]
    assert fields["email"]["x-soar-contains"] == ["email"]
    assert fields["email"]["examples"] == ["person@example.com"]
    assert "default" not in fields["email"]
    assert "anyOf" not in fields["email"]
    assert fields["count"]["type"] == ["integer", "null"]
    assert fields["count"]["title"] == "Count"
    assert fields["count"]["x-soar-column-order"] == 0
    assert "column_name" not in fields["count"]
    assert "column_order" not in fields["count"]
    assert fields["ratio"]["type"] == ["number", "null"]
    assert fields["enabled"]["type"] == ["boolean", "null"]
    assert fields["values"]["items"]["type"] == ["string", "null"]
    assert fields["required_nullable"]["type"] == ["string", "null"]
    assert schema["$defs"]["NullableOutput"]["required"] == [
        "values",
        "required_nullable",
    ]
    assert schema["$defs"]["NullableParams"]["properties"]["name"]["type"] == [
        "string",
        "null",
    ]
    assert schema["$defs"]["NullableSummary"]["properties"]["count"]["type"] == [
        "integer",
        "null",
    ]


def test_output_schema_compacts_nullable_containers_and_preserves_other_alternatives():
    class NestedOutput(ActionOutput):
        name: str

    class StructuredOutput(ActionOutput):
        label: str | None = Field(default=None, min_length=2)
        nested: NestedOutput | None = None
        tags: list[str] | None = Field(default=None, min_length=1)
        attributes: dict[str, str] | None = None
        restricted: (
            Annotated[list[str], Field(json_schema_extra={"enum": [["allowed"]]})]
            | None
        ) = None
        collection: list[str] | dict[str, str]

    schema = OutputsSerializer.serialize_output_schema(Params, StructuredOutput)
    fields = schema["$defs"]["StructuredOutput"]["properties"]

    assert fields["label"]["anyOf"] == [
        {"type": "string", "minLength": 2},
        {"type": "null"},
    ]
    assert fields["nested"]["anyOf"] == [
        {"$ref": "#/$defs/NestedOutput"},
        {"type": "null"},
    ]
    assert fields["tags"]["type"] == ["array", "null"]
    assert fields["tags"]["items"] == {"type": "string"}
    assert fields["tags"]["minItems"] == 1
    assert "default" not in fields["tags"]
    assert "anyOf" not in fields["tags"]
    assert fields["attributes"]["type"] == ["object", "null"]
    assert fields["attributes"]["additionalProperties"] == {"type": "string"}
    assert "anyOf" not in fields["attributes"]
    assert fields["restricted"]["anyOf"] == [
        {"type": "array", "items": {"type": "string"}, "enum": [["allowed"]]},
        {"type": "null"},
    ]
    assert fields["collection"]["anyOf"] == [
        {"type": "array", "items": {"type": "string"}},
        {"type": "object", "additionalProperties": {"type": "string"}},
    ]


def test_output_schema_flattens_nested_type_arrays():
    class MultiTypeOutput(ActionOutput):
        value: str | int | None

    schema = OutputsSerializer.serialize_output_schema(Params, MultiTypeOutput)

    assert schema["$defs"]["MultiTypeOutput"]["properties"]["value"]["type"] == [
        "string",
        "integer",
        "null",
    ]


def test_output_schema_omits_null_defaults_without_changing_values():
    class DefaultParams(Params):
        name: str | None = None

    class DefaultOutput(ActionOutput):
        default: str | None = None
        count: int = 0
        enabled: bool = False
        label: str = ""
        payload: dict = Field(default={"default": None}, examples=[{"default": None}])

    class DefaultSummary(ActionOutput):
        count: int | None = None

    schema = OutputsSerializer.serialize_output_schema(
        DefaultParams, DefaultOutput, DefaultSummary
    )
    fields = schema["$defs"]["DefaultOutput"]["properties"]

    assert "default" not in fields["default"]
    assert fields["default"]["type"] == ["string", "null"]
    assert fields["count"]["default"] == 0
    assert fields["enabled"]["default"] is False
    assert fields["label"]["default"] == ""
    assert fields["payload"]["default"] == {"default": None}
    assert fields["payload"]["examples"] == [{"default": None}]
    assert "default" not in schema["$defs"]["DefaultParams"]["properties"]["name"]
    assert "default" not in schema["$defs"]["DefaultSummary"]["properties"]["count"]

    assert DefaultParams().name is None
    assert DefaultSummary().count is None
    assert DefaultOutput().model_dump() == {
        "default": None,
        "count": 0,
        "enabled": False,
        "label": "",
        "payload": {"default": None},
    }
    assert DefaultOutput(
        default="provided", count=2, enabled=True, label="provided", payload={}
    ).model_dump() == {
        "default": "provided",
        "count": 2,
        "enabled": True,
        "label": "provided",
        "payload": {},
    }


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
        underscored_field: str = Param(alias="_underscored_field")

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
        "_underscored_field": {
            "name": "underscored_field",
            "description": "Underscored Field",
            "data_type": "string",
            "required": True,
            "primary": False,
            "allow_list": False,
            "order": 7,
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
        {
            "data_path": "summary.total_objects",
            "data_type": "numeric",
            "example_values": [1],
        },
        {
            "data_path": "summary.total_objects_successful",
            "data_type": "numeric",
            "example_values": [1],
        },
    ]


def test_outputs_serialize_output_class():
    class SampleNestedOutput(ActionOutput):
        bool_value: bool = OutputField(column_name="Nested Value")

    class SampleOutput(ActionOutput):
        string_value: str
        int_value: int
        list_value: list[str]
        cef_value: str = OutputField(
            cef_types=["ip"],
            example_values=["1.1.1.1"],
            column_name="CEF Value",
        )
        nested_value: SampleNestedOutput
        underscored_value: str = OutputField(alias="_underscored_value")

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
            "column_name": "CEF Value",
            "column_order": 0,
        },
        {
            "data_path": "action_result.data.*.nested_value.bool_value",
            "data_type": "boolean",
            "example_values": [True, False],
            "column_name": "Nested Value",
            "column_order": 1,
        },
        {
            "data_path": "action_result.data.*._underscored_value",
            "data_type": "string",
        },
        {
            "data_path": "summary.total_objects",
            "data_type": "numeric",
            "example_values": [1],
        },
        {
            "data_path": "summary.total_objects_successful",
            "data_type": "numeric",
            "example_values": [1],
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
            "example_values": [True, False],
        },
        {
            "data_path": "summary.total_objects",
            "data_type": "numeric",
            "example_values": [1],
        },
        {
            "data_path": "summary.total_objects_successful",
            "data_type": "numeric",
            "example_values": [1],
        },
    ]


def test_serialize_parameter_datapaths():
    class SampleParams(Params):
        cef_value: str = Param(cef_types=["user name"], column_name="CEF Value")

    serialized_parameter_datapaths = list(
        OutputsSerializer.serialize_parameter_datapaths(SampleParams)
    )

    assert serialized_parameter_datapaths == [
        {
            "data_path": "action_result.parameter.cef_value",
            "data_type": "string",
            "contains": ["user name"],
            "column_name": "CEF Value",
            "column_order": 0,
        },
    ]


def test_serialize_parameter_datapaths_with_none_annotation():
    class SampleParams(Params):
        field_with_type: str

    SampleParams.model_fields["field_with_type"].annotation = None

    serialized_parameter_datapaths = list(
        OutputsSerializer.serialize_parameter_datapaths(SampleParams)
    )

    assert serialized_parameter_datapaths == []


def test_serilized_datapaths_params():
    class SampleParams(Params):
        int_value: int
        str_value: str
        bool_value: bool
        cef_value: str = Param(cef_types=["user name"], column_name="CEF Value")

    class SampleOutput(ActionOutput):
        string_value: str = OutputField(column_name="String Value")

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
            "column_name": "CEF Value",
            "column_order": 0,
        },
        {
            "data_path": "action_result.data.*.string_value",
            "data_type": "string",
            "column_name": "String Value",
            "column_order": 1,
        },
        {
            "data_path": "summary.total_objects",
            "data_type": "numeric",
            "example_values": [1],
        },
        {
            "data_path": "summary.total_objects_successful",
            "data_type": "numeric",
            "example_values": [1],
        },
    ]


def test_input_schema_preserves_parameter_rules_aliases_and_soar_hints():
    class LookupParams(Params):
        domain: str = Param(
            alias="hostname", cef_types=["domain"], primary=True, column_name="Domain"
        )
        note: str | None = Param(required=False, allow_list=True)
        token: str = Param(sensitive=True)
        count: int = Param(default=0)

    schema = ParamsSerializer.serialize_input_schema(LookupParams)
    fields = schema["properties"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["required"] == ["hostname", "token"]
    assert fields["hostname"]["title"] == "Domain"
    assert fields["hostname"]["x-soar-contains"] == ["domain"]
    assert fields["hostname"]["x-soar-primary"] is True
    assert fields["hostname"]["x-soar-order"] == 0
    assert fields["note"]["x-soar-allow-list"] is True
    assert fields["note"]["type"] == ["string", "null"]
    assert "default" not in fields["note"]
    assert "required" not in fields["note"]
    assert fields["token"]["writeOnly"] is True
    assert fields["count"]["default"] == 0
