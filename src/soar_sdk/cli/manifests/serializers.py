__lazy_modules__ = {
    "collections.abc",
    "itertools",
    "logging",
    "pydantic",
    "pydantic.json_schema",
    "pydantic_core",
    "soar_sdk.action_results",
    "soar_sdk.field_utils",
    "soar_sdk.meta.datatypes",
    "soar_sdk.params",
    "types",
    "typing",
}

import itertools
from collections.abc import Iterator
from logging import getLogger
from types import GenericAlias
from typing import Any, Literal

from pydantic import Field, create_model
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema

from soar_sdk.action_results import ActionOutput, OutputFieldSpecification
from soar_sdk.field_utils import normalize_field_annotation, parse_json_schema_extra
from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.params import Params

logger = getLogger(__name__)

_NULLABLE_CONTAINER_KEYWORDS = {
    "type",
    "title",
    "description",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "uniqueItems",
    "contains",
    "minContains",
    "maxContains",
    "unevaluatedItems",
    "properties",
    "patternProperties",
    "additionalProperties",
    "propertyNames",
    "required",
    "minProperties",
    "maxProperties",
    "dependentRequired",
    "dependentSchemas",
    "unevaluatedProperties",
}


class _ActionSchemaGenerator(GenerateJsonSchema):
    """Use compact type arrays and omit null default annotations."""

    def default_schema(self, schema: core_schema.WithDefaultSchema) -> JsonSchemaValue:
        """Keep runtime defaults while omitting null from the schema metadata."""
        generated = super().default_schema(schema)
        if generated.get("default") is None:
            generated.pop("default", None)
        return generated

    def get_flattened_anyof(self, schemas: list[JsonSchemaValue]) -> JsonSchemaValue:
        """Compact alternatives whose constraints still allow the same values."""
        if schemas and all(set(schema) == {"type"} for schema in schemas):
            types: list[str] = []
            for schema in schemas:
                schema_types = schema["type"]
                types.extend(
                    schema_types if isinstance(schema_types, list) else [schema_types]
                )
            return {"type": list(dict.fromkeys(types))}
        if len(schemas) == 2 and schemas[1] == {"type": "null"}:
            container = schemas[0]
            if (
                container.get("type") in ("array", "object")
                and container.keys() <= _NULLABLE_CONTAINER_KEYWORDS
            ):
                return {**container, "type": [container["type"], "null"]}
        return super().get_flattened_anyof(schemas)


def _normalize_schema_metadata(schema: Any) -> None:  # noqa: ANN401
    """Preserve SOAR hints without rewriting literal defaults or examples."""
    if not isinstance(schema, dict):
        return
    for legacy, native in (
        ("cef_types", "x-soar-contains"),
        ("column_name", "title"),
        ("column_order", "x-soar-column-order"),
        ("primary", "x-soar-primary"),
        ("order", "x-soar-order"),
        ("allow_list", "x-soar-allow-list"),
    ):
        if legacy in schema:
            schema[native] = schema.pop(legacy)
    if isinstance(schema.get("required"), bool):
        schema.pop("required")
    if schema.pop("sensitive", False):
        schema["writeOnly"] = True
    for key, child in schema.items():
        if key in (
            "properties",
            "patternProperties",
            "$defs",
            "definitions",
            "dependentSchemas",
        ):
            for nested in child.values():
                _normalize_schema_metadata(nested)
        elif key in (
            "items",
            "additionalProperties",
            "unevaluatedProperties",
            "propertyNames",
            "contains",
            "unevaluatedItems",
            "not",
            "if",
            "then",
            "else",
        ):
            _normalize_schema_metadata(child)
        elif key in ("anyOf", "oneOf", "allOf", "prefixItems"):
            for nested in child:
                _normalize_schema_metadata(nested)


class ParamsSerializer:
    """Serializes Params classes to JSON schema."""

    @staticmethod
    def serialize_input_schema(params_class: type[Params]) -> dict[str, Any]:
        """Describe action inputs as JSON Schema Draft 2020-12."""
        schema = params_class.model_json_schema(
            by_alias=True, schema_generator=_ActionSchemaGenerator
        )
        schema.pop("title", None)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        for order, (name, field) in enumerate(params_class.model_fields.items()):
            schema["properties"][field.alias or name]["x-soar-order"] = order
        _normalize_schema_metadata(schema)
        return schema

    @staticmethod
    def get_sorted_fields_keys(params_class: type[Params]) -> list[str]:
        """Lists the fields of a Params class in order of declaration."""
        return list(params_class.model_fields.keys())

    @classmethod
    def serialize_fields_info(cls, params_class: type[Params]) -> dict[str, Any]:
        """Serializes the fields of a Params class to JSON schema."""
        return params_class._to_json_schema()


class OutputsSerializer:
    """Serializes ActionOutput classes to JSON schema."""

    @staticmethod
    def serialize_output_schema(
        params_class: type[Params],
        outputs_class: type[ActionOutput],
        summary_class: type[ActionOutput] | None = None,
    ) -> dict[str, Any]:
        """Describe an action result directly as JSON Schema Draft 2020-12."""
        result_model = create_model(
            "ActionResultOutputSchema",
            status=(
                Literal["success", "failure"],
                Field(default_factory=lambda: "success"),
            ),
            message=(str, Field(default_factory=str)),
            parameter=(params_class, Field(default_factory=params_class)),
            context=(dict[str, Any], Field(default_factory=dict)),
            data=(GenericAlias(list, outputs_class), Field(default_factory=list)),
            extra_data=(list[dict[str, Any]], Field(default_factory=list)),
            summary=(summary_class or dict[str, Any], Field(default_factory=dict)),
        )
        schema = result_model.model_json_schema(
            by_alias=True,
            mode="serialization",
            schema_generator=_ActionSchemaGenerator,
        )
        schema.pop("title", None)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["additionalProperties"] = True
        schema["properties"]["result_summary"] = {
            "type": "object",
            "properties": {
                "total_objects": {"type": "number", "examples": [1]},
                "total_objects_successful": {"type": "number", "examples": [1]},
            },
            "additionalProperties": True,
        }

        _normalize_schema_metadata(schema)
        return schema

    @staticmethod
    def serialize_parameter_datapaths(
        params_class: type[Params],
        column_order_counter: itertools.count | None = None,
    ) -> Iterator[OutputFieldSpecification]:
        """Serializes the parameter data paths of a Params class to JSON schema."""
        if column_order_counter is None:
            column_order_counter = itertools.count()

        for field_name, field in params_class.model_fields.items():
            annotation = field.annotation
            if annotation is None:
                continue

            normalized = normalize_field_annotation(
                annotation,
                field_name=field_name,
                context="Action parameter",
                allow_list=False,
            )

            parameter_name = field.alias or field_name

            spec = OutputFieldSpecification(
                data_path=f"action_result.parameter.{parameter_name}",
                data_type=as_datatype(normalized.base_type),
            )

            json_schema_extra = parse_json_schema_extra(field.json_schema_extra)

            if cef_types := json_schema_extra.get("cef_types"):
                spec["contains"] = cef_types

            column_name = json_schema_extra.get("column_name")

            if column_name is not None:
                spec["column_name"] = column_name
                spec["column_order"] = next(column_order_counter)
            yield spec

    @classmethod
    def serialize_datapaths(
        cls,
        params_class: type[Params],
        outputs_class: type[ActionOutput],
        summary_class: type[ActionOutput] | None = None,
    ) -> list[OutputFieldSpecification]:
        """Serializes the data paths of an action to JSON schema."""
        status = OutputFieldSpecification(
            data_path="action_result.status",
            data_type="string",
            example_values=["success", "failure"],
        )
        message = OutputFieldSpecification(
            data_path="action_result.message",
            data_type="string",
        )
        column_order_counter = itertools.count()
        params = cls.serialize_parameter_datapaths(params_class, column_order_counter)
        outputs = outputs_class._to_json_schema(
            column_order_counter=column_order_counter
        )
        summary = (
            summary_class._to_json_schema("action_result.summary", column_order_counter)
            if summary_class
            else []
        )
        object_counts = [
            OutputFieldSpecification(
                data_path="summary.total_objects",
                data_type="numeric",
                example_values=[1],
            ),
            OutputFieldSpecification(
                data_path="summary.total_objects_successful",
                data_type="numeric",
                example_values=[1],
            ),
        ]
        return [status, message, *params, *outputs, *summary, *object_counts]
