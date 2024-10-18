from typing import Any

from pydantic.fields import ModelField

from soar_sdk.params import Params


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
    def get_sorted_fields_keys(params_klass: type[Params]) -> list[str]:
        return sorted(
            params_klass.__fields__.keys(),
            key=lambda field: params_klass.__fields__[field].field_info.extra.get(  # type: ignore
                "order"
            ),
        )

    @classmethod
    def serialize_fields_info(cls, params_klass: type[Params]) -> dict[str, Any]:
        return {
            params_klass.__fields__[field].name: cls.serialize_field_info(
                params_klass.__fields__[field]
            )
            for field in cls.get_sorted_fields_keys(params_klass)
            # FIXME: we should use model_fields in pydantic 2+
        }
