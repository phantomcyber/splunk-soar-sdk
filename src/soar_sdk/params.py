from typing import Any, ClassVar, NotRequired

from pydantic import Field
from pydantic.main import BaseModel
from pydantic_core import PydanticUndefined
from typing_extensions import TypedDict

from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.field_utils import parse_json_schema_extra
from soar_sdk.meta.datatypes import as_datatype

remove_when_soar_newer_than(
    "7.0.0", "NotRequired from typing_extensions is in typing in Python 3.11+"
)

MAX_COUNT_VALUE = 4294967295


def Param(
    description: str | None = None,
    required: bool = True,
    primary: bool = False,
    default: Any | None = None,  # noqa: ANN401
    value_list: list | None = None,
    cef_types: list | None = None,
    allow_list: bool = False,
    sensitive: bool = False,
    alias: str | None = None,
    column_name: str | None = None,
) -> Any:  # noqa: ANN401
    """Representation of a single complex action parameter.

    Use this function to define the default value for an action parameter that requires
    extra metadata for the manifest. This function is a thin wrapper around pydantic.Field.

    :param description: A short description of this parameter.
      The description is shown in the user interface when running an action manually.
    :param default: To set the default value of a variable in the UI, use this key.
      The user will be able to modify this value, so the app will need to validate it.
      This key also works in conjunction with value_list.
    :param required: Whether or not this parameter is mandatory for this action
      to function. If this parameter is not provided, the action fails.
    :param primary: Specifies if the action acts primarily on this parameter or not.
      It is used in conjunction with the contains field to display a list of contextual
      actions where the user clicks on a piece of data in the UI.
    :param value_list: To allow the user to choose from a pre-defined list of values
      displayed in a drop-down for this parameter, specify them as a list for example,
      ["one", "two", "three"]. An action can be run from the playbook, in which case
      the user can pass an arbitrary value for the parameter, so the app needs
      to validate this parameter on its own.
    :param contains: Specifies what kind of content this field contains.
    :param data_type: 	The type of variable. Supported types are string, password,
      numeric, and boolean.
    :param allow_list: Use this key to specify if the parameter supports specifying
      multiple values as a comma separated string.
    :param kwargs: additional kwargs accepted by pydantic.Field
    :param column_name: Optional name for the parameter when displayed in an output table.
    :return: returns the FieldInfo object as pydantic.Field
    """
    json_schema_extra: dict[str, Any] = {}
    if required is not None:
        json_schema_extra["required"] = required
    if primary is not None:
        json_schema_extra["primary"] = primary
    if value_list:
        json_schema_extra["value_list"] = value_list
    if cef_types is not None:
        json_schema_extra["cef_types"] = cef_types
    if allow_list is not None:
        json_schema_extra["allow_list"] = allow_list
    if sensitive is not None:
        json_schema_extra["sensitive"] = sensitive
    if column_name is not None:
        json_schema_extra["column_name"] = column_name

    # Use ... for required fields
    field_default: Any = ... if default is None and required else default

    return Field(
        default=field_default,
        description=description,
        alias=alias,
        json_schema_extra=json_schema_extra if json_schema_extra else None,
    )


class InputFieldSpecification(TypedDict):
    """Canonical data format for the JSON dictionary given to action runs by the SOAR platform."""

    order: int
    name: str
    description: str
    data_type: str
    contains: NotRequired[list[str]]
    required: bool
    primary: bool
    value_list: NotRequired[list[str]]
    allow_list: bool
    default: NotRequired[str | int | float | bool]
    column_name: NotRequired[str]
    column_order: NotRequired[int]


class Params(BaseModel):
    """Params defines the full set of inputs for an action.

    It can contain strings, booleans, or numbers -- no lists or dictionaries.
    Params fields can be optional if desired, or optionally have a default value, CEF type, and other metadata defined in :func:`soar_sdk.params.Param`.
    """

    @staticmethod
    def _default_field_description(field_name: str) -> str:
        words = field_name.split("_")
        return " ".join(words).title()

    @classmethod
    def _to_json_schema(cls) -> dict[str, InputFieldSpecification]:
        params: dict[str, InputFieldSpecification] = {}

        for field_order, (field_name, field) in enumerate(cls.model_fields.items()):
            field_type = field.annotation

            if field_type is None:
                raise TypeError(f"Parameter {field_name} has no type annotation")

            try:
                type_name = as_datatype(field_type)
            except TypeError as e:
                raise TypeError(
                    f"Failed to serialize action parameter {field_name}: {e}"
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

            params_field = InputFieldSpecification(
                order=field_order,
                name=field_name,
                description=description,
                data_type=type_name,
                required=bool(json_schema_extra.get("required", True)),
                primary=bool(json_schema_extra.get("primary", False)),
                allow_list=bool(json_schema_extra.get("allow_list", False)),
            )

            if cef_types := json_schema_extra.get("cef_types"):
                params_field["contains"] = cef_types
            if (default := field.default) not in (PydanticUndefined, None):
                params_field["default"] = default
            if value_list := json_schema_extra.get("value_list"):
                params_field["value_list"] = value_list

            params[field.alias or field_name] = params_field

        return params


class OnPollParams(Params):
    """Canonical parameters for the special 'on poll' action."""

    start_time: int = Param(
        description="Start of time range, in epoch time (milliseconds).",
        required=False,
    )

    end_time: int = Param(
        description="End of time range, in epoch time (milliseconds).",
        required=False,
    )

    container_count: int = Param(
        description="Maximum number of container records to query for.",
        required=False,
    )

    artifact_count: int = Param(
        description="Maximum number of artifact records to query for.",
        required=False,
    )

    container_id: str = Param(
        description="Comma-separated list of container IDs to limit the ingestion to.",
        required=False,
        allow_list=True,
    )

    def is_manual_poll(self) -> bool:
        """Check if this is a manual poll execution (poll now) vs scheduled polling."""
        if not self.container_count:
            return False
        return int(self.container_count) != MAX_COUNT_VALUE


class OnESPollParams(Params):
    """Canonical parameters for the special 'on es poll' action."""

    start_time: int = Param(
        description="Start of time range, in epoch time (milliseconds).",
        required=False,
    )
    end_time: int = Param(
        description="End of time range, in epoch time (milliseconds).",
        required=False,
    )
    container_count: int = Param(
        description="Maximum number of container records to query for.",
        required=False,
    )

    es_base_url: str = Param(
        description="Base URL for the Splunk Enterprise Security API",
        required=True,
    )
    es_session_key: str = Param(
        description="Session token for the Splunk Enterprise Security API",
        required=True,
    )


class MakeRequestParams(Params):
    """Canonical parameters for the special make request action."""

    # Define allowed field names for subclasses
    _ALLOWED_FIELDS: ClassVar[set[str]] = {
        "http_method",
        "endpoint",
        "headers",
        "query_parameters",
        "body",
        "timeout",
        "verify_ssl",
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        """Validate that subclasses only define allowed fields."""
        super().__init_subclass__(**kwargs)

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        """Ensure model fields are validated after instance is created."""
        super().model_post_init(__context)
        # Check if any fields are not in the allowed set
        invalid_fields = (
            set(self.__class__.model_fields.keys()) - self.__class__._ALLOWED_FIELDS
        )
        if invalid_fields:
            raise TypeError(
                f"MakeRequestParams subclass '{self.__class__.__name__}' can only define these fields: "
                f"{sorted(self.__class__._ALLOWED_FIELDS)}. Invalid fields: {sorted(invalid_fields)}"
            )

    http_method: str = Param(
        description="The HTTP method to use for the request.",
        required=True,
        value_list=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )

    endpoint: str = Param(
        description="The endpoint to send the request to.",
        required=True,
    )

    headers: str = Param(
        description="The headers to send with the request (JSON object). An example is {'Content-Type': 'application/json'}",
        required=False,
    )

    query_parameters: str = Param(
        description="Parameters to append to the URL (JSON object or query string). An example is ?key=value&key2=value2",
        required=False,
    )

    body: str = Param(
        description="The body to send with the request (JSON object). An example is {'key': 'value', 'key2': 'value2'}",
        required=False,
    )

    timeout: int = Param(
        description="The timeout for the request in seconds.",
        required=False,
    )

    verify_ssl: bool = Param(
        description="Whether to verify the SSL certificate. Default is False.",
        required=False,
        default=False,
    )
