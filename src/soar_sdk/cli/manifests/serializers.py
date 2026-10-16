__lazy_modules__ = {
    "collections.abc",
    "itertools",
    "logging",
    "soar_sdk.action_results",
    "soar_sdk.field_utils",
    "soar_sdk.meta.datatypes",
    "soar_sdk.params",
    "typing",
}

import itertools
from collections.abc import Iterator
from logging import getLogger
from types import GenericAlias
from typing import Any, Literal

from pydantic import Field, create_model

from soar_sdk.action_results import ActionOutput, OutputFieldSpecification
from soar_sdk.field_utils import normalize_field_annotation, parse_json_schema_extra
from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.params import Params

logger = getLogger(__name__)


class ParamsSerializer:
    """Serializes Params classes to JSON schema."""

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
        schema = result_model.model_json_schema(by_alias=True, mode="serialization")
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

        def normalize_metadata(value: Any) -> None:  # noqa: ANN401
            if isinstance(value, dict):
                if "cef_types" in value:
                    value["x-soar-contains"] = value.pop("cef_types")
                if "column_name" in value:
                    value["title"] = value.pop("column_name")
                if "column_order" in value:
                    value["x-soar-column-order"] = value.pop("column_order")
                for child in value.values():
                    normalize_metadata(child)
            elif isinstance(value, list):
                for child in value:
                    normalize_metadata(child)

        normalize_metadata(schema)
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
