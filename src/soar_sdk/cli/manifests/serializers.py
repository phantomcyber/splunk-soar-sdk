from typing import Any, Iterator

from pydantic.fields import ModelField

from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput, OutputFieldSpecification


class ParamsSerializer:
    @staticmethod
    def serialize_field_info(field: ModelField) -> dict[str, Any]:
        extra = field.field_info.extra
        return {
            "name": field.name,
            "description": field.field_info.description,
            "data_type": extra.get("data_type"),
            "contains": extra.get("contains"),
            "required": extra.get("required", False),
            "primary": extra.get("primary", False),
            "values_list": extra.get("values_list"),
            "allow_list": extra.get("allow_list", False),
            "default": field.default,
            "order": extra.get("order"),
        }

    @staticmethod
    def get_sorted_fields_keys(params_class: type[Params]) -> list[str]:
        return sorted(
            params_class.__fields__.keys(),
            key=lambda field: params_class.__fields__[field].field_info.extra.get(  # type: ignore
                "order"
            ),
        )

    @classmethod
    def serialize_fields_info(cls, params_class: type[Params]) -> dict[str, Any]:
        return {
            params_class.__fields__[field].name: cls.serialize_field_info(
                params_class.__fields__[field]
            )
            for field in cls.get_sorted_fields_keys(params_class)
            # FIXME: we should use model_fields in pydantic 2+
        }


class OutputsSerializer:
    @staticmethod
    def serialize_parameter_datapaths(
        params_class: type[Params],
    ) -> Iterator[OutputFieldSpecification]:
        for field_name, field in params_class.__fields__.items():
            spec = OutputFieldSpecification(
                data_path=f"action_result.parameter.{field_name}",
                type=field.field_info.extra["data_type"],
            )
            if cef_types := field.field_info.extra.get("contains"):
                spec["contains"] = cef_types
            yield spec

    @classmethod
    def serialize_datapaths(
        cls, params_class: type[Params], outputs_class: type[ActionOutput]
    ) -> list[OutputFieldSpecification]:
        status = OutputFieldSpecification(
            data_path="action_result.status",
            type="string",
            example_values=["success", "failure"],
        )
        message = OutputFieldSpecification(
            data_path="action_result.message",
            type="string",
        )
        params = cls.serialize_parameter_datapaths(params_class)
        outputs = outputs_class._to_json_schema()
        return [status, message, *params, *outputs]
