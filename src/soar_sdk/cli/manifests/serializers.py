import itertools
from collections.abc import Iterator
from logging import getLogger
from typing import Any

from soar_sdk.action_results import ActionOutput, OutputFieldSpecification
from soar_sdk.field_utils import parse_json_schema_extra
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

            spec = OutputFieldSpecification(
                data_path=f"action_result.parameter.{field_name}",
                data_type=as_datatype(annotation),
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
