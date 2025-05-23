from typing import Optional, TypedDict, Union, Any
from typing_extensions import NotRequired

from pydantic.fields import Field, Undefined
from pydantic.main import BaseModel

from soar_sdk.meta.datatypes import as_datatype


def Param(
    description: Optional[str] = None,
    required: bool = True,
    primary: bool = False,
    default: Optional[str] = None,
    value_list: Optional[list] = None,
    cef_types: Optional[list] = None,
    allow_list: bool = False,
    sensitive: bool = False,
) -> Any:  # noqa: ANN401
    """
    Representation of the param passed into the action. The param needs extra meta
    information that is later used for the configuration of the app and use in
    playbooks. This function takes care of the required information for the manifest
    JSON file and fills in defaults.

    :param order: The order key, starting at 0, allows the app
      author to control the display order of the controls in the UI.
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
    :return: returns the FieldInfo object as pydantic.Field
    """
    if value_list is None:
        value_list = []

    return Field(
        default=default,
        description=description,
        required=required,
        primary=primary,
        value_list=value_list,
        cef_types=cef_types,
        allow_list=allow_list,
        sensitive=sensitive,
    )


class InputFieldSpecification(TypedDict):
    order: int
    name: str
    description: str
    data_type: str
    contains: NotRequired[list[str]]
    required: bool
    primary: bool
    value_list: NotRequired[list[str]]
    allow_list: bool
    default: NotRequired[Union[str, int, float, bool]]


class Params(BaseModel):
    """
    Params defines the inputs for an action. It can contain strings, booleans, or numbers -- no lists or dictionaries.

    Params fields can be optional if desired, or optionally have a default value, CEF type, and other metadata defined in soar_sdk.params.Param.
    """

    @staticmethod
    def _default_field_description(field_name: str) -> str:
        words = field_name.split("_")
        return " ".join(words).title()

    @classmethod
    def _to_json_schema(cls) -> dict[str, InputFieldSpecification]:
        params: dict[str, InputFieldSpecification] = {}

        for field_order, (field_name, field) in enumerate(cls.__fields__.items()):
            field_type = field.annotation

            try:
                type_name = as_datatype(field_type)
            except TypeError as e:
                raise TypeError(
                    f"Failed to serialize action parameter {field_name}: {e}"
                ) from None

            if field.field_info.extra.get("sensitive", False):
                if field_type is not str:
                    raise TypeError(
                        f"Sensitive parameter {field_name} must be type str, not {field_type.__name__}"
                    )
                type_name = "password"

            if not (description := field.field_info.description):
                description = cls._default_field_description(field_name)

            params_field = InputFieldSpecification(
                order=field_order,
                name=field_name,
                description=description,
                data_type=type_name,
                required=field.field_info.extra.get("required", True),
                primary=field.field_info.extra.get("primary", False),
                allow_list=field.field_info.extra.get("allow_list", False),
            )

            if cef_types := field.field_info.extra.get("cef_types"):
                params_field["contains"] = cef_types
            if (default := field.field_info.default) and default != Undefined:
                params_field["default"] = default
            if value_list := field.field_info.extra.get("value_list"):
                params_field["value_list"] = value_list

            params[field_name] = params_field

        return params


class OnPollParams(Params):
    """
    Parameters for on_poll.

    Used to define the specific parameters for the on_poll action.
    """

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
