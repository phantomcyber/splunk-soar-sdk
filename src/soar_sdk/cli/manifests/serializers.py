from typing import Any
from collections.abc import Iterator

from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput, OutputFieldSpecification


class ParamsSerializer:
    @staticmethod
    def get_sorted_fields_keys(params_class: type[Params]) -> list[str]:
        return list(params_class.__fields__.keys())

    @classmethod
    def serialize_fields_info(cls, params_class: type[Params]) -> dict[str, Any]:
        return params_class._to_json_schema()


class OutputsSerializer:
    @staticmethod
    def serialize_parameter_datapaths(
        params_class: type[Params],
    ) -> Iterator[OutputFieldSpecification]:
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
        cls, params_class: type[Params], outputs_class: type[ActionOutput]
    ) -> list[OutputFieldSpecification]:
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
        return [status, message, *params, *outputs]
