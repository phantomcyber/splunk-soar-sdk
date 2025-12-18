from enum import Enum
from typing import Any, NotRequired
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticUndefined
from typing_extensions import TypedDict

from soar_sdk.asset_state import AssetState
from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.exceptions import AppContextRequired
from soar_sdk.field_utils import parse_json_schema_extra
from soar_sdk.input_spec import AppConfig
from soar_sdk.meta.datatypes import as_datatype

remove_when_soar_newer_than(
    "7.0.0", "NotRequired from typing_extensions is in typing in Python 3.11+"
)


class FieldCategory(str, Enum):
    """Categories used to group asset configuration fields in the SOAR UI."""

    CONNECTIVITY = "connectivity"
    ACTION = "action"
    INGEST = "ingest"


def AssetField(
    description: str | None = None,
    required: bool = True,
    default: Any | None = None,  # noqa: ANN401
    value_list: list | None = None,
    sensitive: bool = False,
    alias: str | None = None,
    category: FieldCategory = FieldCategory.CONNECTIVITY,
) -> Any:  # noqa: ANN401
    """Define an asset configuration field with SOAR-specific metadata.

    Args:
        description: Human-friendly label for the field shown in the asset form.
        required: Whether the field must be provided. When True and ``default`` is
            ``None``, the field is marked as required in the manifest.
        default: Default value for optional fields. Ignored when ``required`` is
            True and no explicit default is provided.
        value_list: Optional dropdown options presented to the user.
        sensitive: Marks the field as secret so it is encrypted and hidden from logs.
        alias: Alternate name to emit in the manifest instead of the attribute name.
        category: Grouping used to organize fields in the SOAR UI.

    Returns:
        A Pydantic ``Field`` carrying the metadata needed for manifest generation.
    """
    json_schema_extra: dict[str, Any] = {"category": category}
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
        json_schema_extra=json_schema_extra,
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
    category: FieldCategory
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
        the SOAR platform to avoid conflicts with internal fields. The runtime
        attaches ``auth_state``, ``cache_state``, and ``ingest_state`` when an
        app context is available; accessing them without that context raises
        ``AppContextRequired``.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @model_validator(mode="before")
    @classmethod
    def validate_no_reserved_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Prevent subclasses from using names reserved by the platform.

        The validator inspects annotated field names to ensure they do not start
        with ``_reserved_`` and do not collide with fields injected by the SOAR
        service (see ``AppConfig``). The ``values`` argument is unused but kept
        for Pydantic compatibility.

        Raises:
            ValueError: If a reserved or injected field name is used.
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
        """Generate manifest-ready schema entries from the asset definition.

        Each field is converted into a SOAR manifest dictionary that includes the
        data type, requirement flag, default value, dropdown options, and an order
        index. Alias names are honored when present. Sensitive fields are emitted
        as ``password`` data types and must be annotated as ``str``. Defaults are
        serialized directly, with ``ZoneInfo`` defaults represented by their key.

        Returns:
            Mapping of field (or alias) names to schema specifications.

        Raises:
            TypeError: If a field type cannot be serialized or a sensitive field is
                not declared as ``str``.
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
                category=json_schema_extra.get("category", FieldCategory.CONNECTIVITY),
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
        """Return attribute names marked as sensitive (aliases are ignored)."""
        return {
            field_name
            for field_name, field in cls.model_fields.items()
            if isinstance(field.json_schema_extra, dict)
            and field.json_schema_extra.get("sensitive", False)
        }

    @classmethod
    def timezone_fields(cls) -> set[str]:
        """Return attribute names typed as ``ZoneInfo`` (aliases are ignored)."""
        return {
            field_name
            for field_name, field in cls.model_fields.items()
            if field.annotation is ZoneInfo
        }

    _auth_state: AssetState | None = None
    _cache_state: AssetState | None = None
    _ingest_state: AssetState | None = None

    @property
    def auth_state(self) -> AssetState:
        """Authentication state persisted by SOAR (encrypted at rest); raises if no app context."""
        if self._auth_state is None:
            raise AppContextRequired()
        return self._auth_state

    @property
    def cache_state(self) -> AssetState:
        """Cache for miscellaneous data persisted by SOAR (encrypted at rest); raises if no app context."""
        if self._cache_state is None:
            raise AppContextRequired()
        return self._cache_state

    @property
    def ingest_state(self) -> AssetState:
        """Ingestion checkpoints persisted by SOAR (encrypted at rest); raises if no app context."""
        if self._ingest_state is None:
            raise AppContextRequired()
        return self._ingest_state
