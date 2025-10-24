from typing import Any
from zoneinfo import ZoneInfo
from pydantic import BaseModel, model_validator, ConfigDict, Field
from pydantic_core import PydanticUndefined

from typing_extensions import TypedDict
from typing import NotRequired


from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.meta.datatypes import as_datatype
from soar_sdk.input_spec import AppConfig
from soar_sdk.field_utils import parse_json_schema_extra

remove_when_soar_newer_than(
    "7.0.0", "NotRequired from typing_extensions is in typing in Python 3.11+"
)


def AssetField(
    description: str | None = None,
    required: bool = True,
    default: Any | None = None,  # noqa: ANN401
    value_list: list | None = None,
    sensitive: bool = False,
    alias: str | None = None,
) -> Any:  # noqa: ANN401
    """Representation of an asset configuration field.

    The field needs extra metadata that is later used for the configuration of the app.
    This function takes care of the required information for the manifest JSON file and fills in defaults.

    Args:
        description: A short description of this parameter. The description is shown
            in the asset form as the input's title.
        required: Whether or not this config key is mandatory for this asset to function.
            If this configuration is not provided, actions cannot be executed on the app.
        value_list: To allow the user to choose from a pre-defined list of values
            displayed in a drop-down for this configuration key, specify them as a list
            for example, ["one", "two", "three"].
        sensitive: When True, the field is treated as a password and will be encrypted
            and hidden from logs.

    Returns:
        The FieldInfo object as pydantic.Field.
    """
    json_schema_extra: dict[str, Any] = {}
    if required is not None:
        json_schema_extra["required"] = required
    if value_list is not None:
        json_schema_extra["value_list"] = value_list
    if sensitive is not None:
        json_schema_extra["sensitive"] = sensitive

    # Use ... for required fields
    field_default: Any = ... if default is None and required else default

    return Field(
        default=field_default,
        description=description,
        alias=alias,
        json_schema_extra=json_schema_extra if json_schema_extra else None,
    )


class AssetFieldSpecification(TypedDict):
    """Type specification for asset field metadata.

    This TypedDict defines the structure of asset field specifications used
    in the SOAR manifest JSON format. It contains all the metadata needed
    to describe an asset configuration field for the SOAR platform.

    Attributes:
        data_type: The data type of the field (e.g., "string", "numeric", "boolean").
        description: Optional human-readable description of the field.
        required: Optional flag indicating if the field is mandatory.
        default: Optional default value for the field.
        value_list: Optional list of allowed values for dropdown selection.
        order: Optional integer specifying the display order in the UI.
    """

    data_type: str
    description: NotRequired[str]
    required: NotRequired[bool]
    default: NotRequired[str | int | float | bool]
    value_list: NotRequired[list[str]]
    order: NotRequired[int]


class BaseAsset(BaseModel):
    """Base class for asset models in SOAR SDK.

    This class provides the foundation for defining an asset configuration
    for SOAR apps. It extends Pydantic's BaseModel to provide validation,
    serialization, and manifest generation capabilities for asset configurations.

    Asset classes define the configuration parameters that users need to provide
    when setting up an app instance in SOAR. These typically include connection
    details, authentication credentials, and other app-specific settings.

    The class automatically validates field names to prevent conflicts with
    platform-reserved fields and provides methods to generate JSON schemas
    compatible with SOAR's asset configuration system.

    Example:
        >>> class MyAsset(BaseAsset):
        ...     base_url: str = AssetField(description="API base URL", required=True)
        ...     api_key: str = AssetField(
        ...         description="API authentication key", sensitive=True
        ...     )
        ...     timeout: int = AssetField(
        ...         description="Request timeout in seconds", default=30
        ...     )

    Note:
        Field names cannot start with "_reserved_" or use names reserved by
        the SOAR platform to avoid conflicts with internal fields.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @model_validator(mode="before")
    @classmethod
    def validate_no_reserved_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Prevents subclasses from defining fields starting with "_reserved_".

        This validator ensures that asset field names don't conflict with
        platform-reserved fields or internal SOAR configuration fields.

        Args:
            values: Dictionary of field values being validated.

        Returns:
            The validated values dictionary.

        Raises:
            ValueError: If a field name starts with "_reserved_" or conflicts
                with platform-reserved field names.

        Note:
            The SOAR platform injects fields like "_reserved_credential_management"
            into asset configs, so this prevents the entire "_reserved_" namespace
            from being used in user-defined assets.
        """
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
            if field_name in AppConfig.model_fields:
                raise ValueError(
                    f"Field name '{field_name}' is reserved by the platform and cannot be used in an asset"
                )
        return values

    @staticmethod
    def _default_field_description(field_name: str) -> str:
        """Generate a default human-readable description from a field name.

        Converts snake_case field names to Title Case descriptions by splitting
        on underscores and capitalizing each word.

        Args:
            field_name: The field name to convert (e.g., "api_key").

        Returns:
            A title-cased description (e.g., "Api Key").

        Example:
            >>> BaseAsset._default_field_description("base_url")
            'Base Url'
        """
        words = field_name.split("_")
        return " ".join(words).title()

    @classmethod
    def to_json_schema(cls) -> dict[str, AssetFieldSpecification]:
        """Generate a JSON schema representation of the asset configuration.

        Converts the Pydantic model fields into a format compatible with SOAR's
        asset configuration system. This includes data type mapping, validation
        rules, and UI hints for the SOAR platform.

        Returns:
            A dictionary mapping field names to their schema specifications,
            including data types, descriptions, requirements, and other metadata.

        Raises:
            TypeError: If a field type cannot be serialized or if a sensitive
                field is not of type str.

        Example:
            >>> class MyAsset(BaseAsset):
            ...     host: str = AssetField(description="Server hostname")
            ...     port: int = AssetField(description="Server port", default=443)
            >>> schema = MyAsset.to_json_schema()
            >>> schema["host"]["data_type"]
            'string'
            >>> schema["host"]["required"]
            True

        Note:
            Sensitive fields are automatically converted to "password" type
            regardless of their Python type annotation, and must be str type.
        """
        params: dict[str, AssetFieldSpecification] = {}

        for field_order, (field_name, field) in enumerate(cls.model_fields.items()):
            field_type = field.annotation
            if field_type is None:
                continue

            try:
                type_name = as_datatype(field_type)
            except TypeError as e:
                raise TypeError(
                    f"Failed to serialize asset field {field_name}: {e}"
                ) from None

            json_schema_extra = parse_json_schema_extra(field.json_schema_extra)

            if json_schema_extra.get("sensitive", False):
                if field_type is not str:
                    raise TypeError(
                        f"Sensitive parameter {field_name} must be type str, not {field_type.__name__}"
                    )
                type_name = "password"

            if not (description := field.description):
                description = cls._default_field_description(field_name)

            params_field = AssetFieldSpecification(
                data_type=type_name,
                required=bool(json_schema_extra.get("required", True)),
                description=description,
                order=field_order,
            )

            if (default := field.default) not in (PydanticUndefined, None):
                if isinstance(default, ZoneInfo):
                    params_field["default"] = default.key
                else:
                    params_field["default"] = default
            if value_list := json_schema_extra.get("value_list"):
                params_field["value_list"] = value_list

            params[field.alias or field_name] = params_field

        return params

    @classmethod
    def fields_requiring_decryption(cls) -> set[str]:
        """Set of fields that require decryption.

        Returns:
            A set of field names that are marked as sensitive and need
            decryption before use.
        """
        return {
            field_name
            for field_name, field in cls.model_fields.items()
            if isinstance(field.json_schema_extra, dict)
            and field.json_schema_extra.get("sensitive", False)
        }

    @classmethod
    def timezone_fields(cls) -> set[str]:
        """Set of fields that use the ZoneInfo type.

        Returns:
            A set of field names that use the ZoneInfo type.
        """
        return {
            field_name
            for field_name, field in cls.model_fields.items()
            if field.annotation is ZoneInfo
        }
