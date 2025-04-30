from typing import Any, Optional, TypedDict, Union
from pydantic import BaseModel, root_validator
from pydantic.fields import Field, Undefined

from typing_extensions import NotRequired


from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.input_spec import AppConfig


def AssetField(
    description: Optional[str] = None,
    required: bool = True,
    default: Optional[str] = None,
    value_list: Optional[list] = None,
    sensitive: bool = False,
) -> Any:  # noqa: ANN401
    """
    Representation of an asset configuration field. The field needs extra metadata
    that is later used for the configuration of the app. This function takes care of the required
    information for the manifest JSON file and fills in defaults.

    :param description: A short description of this parameter.
      The description is shown in the asset form as the input's title.
    :param required: Whether or not this config key is mandatory for this asset
      to function. If this configuration is not provided, actions cannot be executed on the app.
    :param value_list: To allow the user to choose from a pre-defined list of values
      displayed in a drop-down for this configuration key, specify them as a list for example,
      ["one", "two", "three"].
    :param sensitive: when True, the field is treated as a password and will be encrypted and
      hidden from logs
    :return: returns the FieldInfo object as pydantic.Field
    """
    return Field(
        default=default,
        description=description,
        required=required,
        value_list=value_list,
        sensitive=sensitive,
    )


class AssetFieldSpecification(TypedDict):
    data_type: str
    description: NotRequired[str]
    required: NotRequired[bool]
    default: NotRequired[Union[str, int, float, bool]]
    value_list: NotRequired[list[str]]
    order: NotRequired[int]


class BaseAsset(BaseModel):
    """
    Base class for asset models in SOAR SDK.
    """

    @root_validator(pre=True)
    def validate_no_reserved_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Prevents subclasses from defining fields starting with "_reserved_"."""
        for field_name in cls.__annotations__:
            # The platform injects fields like "_reserved_credential_management" into asset configs,
            # so we just prevent the entire namespace from being used in real assets.
            if field_name.startswith("_reserved_"):
                raise ValueError(
                    f"Field name '{field_name}' starts with '_reserved_' which is not allowed"
                )

            # This accounts for some bad behavior by the platform; it injects a few app-related
            # metadata fields directly into asset configuration dictionaries, which can lead to
            # undefined behavior if an asset tries to use the same field names.
            if field_name in AppConfig.__fields__:
                raise ValueError(
                    f"Field name '{field_name}' is reserved by the platform and cannot be used in an asset"
                )
        return values

    @staticmethod
    def _default_field_description(field_name: str) -> str:
        words = field_name.split("_")
        return " ".join(words).title()

    @classmethod
    def to_json_schema(cls) -> dict[str, AssetFieldSpecification]:
        params: dict[str, AssetFieldSpecification] = {}

        for field_order, (field_name, field) in enumerate(cls.__fields__.items()):
            field_type = field.annotation

            try:
                type_name = as_datatype(field_type)
            except TypeError as e:
                raise TypeError(
                    f"Failed to serialize asset field {field_name}: {e}"
                ) from None

            if field.field_info.extra.get("sensitive", False):
                if field_type is not str:
                    raise TypeError(
                        f"Sensitive parameter {field_name} must be type str, not {field_type.__name__}"
                    )
                type_name = "password"

            if not (description := field.field_info.description):
                description = cls._default_field_description(field_name)

            params_field = AssetFieldSpecification(
                data_type=type_name,
                required=field.field_info.extra.get("required", True),
                description=description,
                order=field_order,
            )

            if (default := field.field_info.default) and default != Undefined:
                params_field["default"] = default
            if value_list := field.field_info.extra.get("value_list"):
                params_field["value_list"] = value_list

            params[field_name] = params_field

        return params
