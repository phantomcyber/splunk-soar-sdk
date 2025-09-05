from typing import Any, Optional
from collections.abc import Iterator
from logging import getLogger

from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput, OutputFieldSpecification

logger = getLogger(__name__)


class ParamsSerializer:
    """Serializes Params classes to JSON schema."""

    @staticmethod
    def get_sorted_fields_keys(params_class: type[Params]) -> list[str]:
        """Lists the fields of a Params class in order of declaration."""
        return list(params_class.__fields__.keys())

    @classmethod
    def serialize_fields_info(cls, params_class: type[Params]) -> dict[str, Any]:
        """Serializes the fields of a Params class to JSON schema."""
        return params_class._to_json_schema()


class OutputsSerializer:
    """Serializes ActionOutput classes to JSON schema."""

    @staticmethod
    def serialize_parameter_datapaths(
        params_class: type[Params],
    ) -> Iterator[OutputFieldSpecification]:
        """Serializes the parameter data paths of a Params class to JSON schema."""
        for field_name, field in params_class.__fields__.items():
            spec = OutputFieldSpecification(
                data_path=f"action_result.parameter.{field_name}",
                data_type=as_datatype(field.annotation),
            )
            if cef_types := field.field_info.extra.get("cef_types"):
                spec["contains"] = cef_types
            yield spec

    @classmethod
    def serialize_datapaths(
        cls,
        params_class: type[Params],
        outputs_class: type[ActionOutput],
        summary_class: Optional[type[ActionOutput]] = None,
    ) -> list[OutputFieldSpecification]:
        """Serializes the data paths of an ActionOutput class to JSON schema."""
        if (
            outputs_class.generate_action_summary_message
            != ActionOutput.generate_action_summary_message
        ):
            logger.warning(
                f"Overriding ActionOutput.generate_action_summary_message is deprecated. Please call SOARClient.set_message from your action handler instead. [in {outputs_class.__name__}]"
            )

        status = OutputFieldSpecification(
            data_path="action_result.status",
            data_type="string",
            example_values=["success", "failure"],
        )
        message = OutputFieldSpecification(
            data_path="action_result.message",
            data_type="string",
        )
        params = cls.serialize_parameter_datapaths(params_class)
        outputs = outputs_class._to_json_schema()
        summary = (
            summary_class._to_json_schema("action_result.summary")
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
