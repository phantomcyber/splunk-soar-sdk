from typing import Optional

from pydantic.fields import Field, FieldInfo
from pydantic.main import BaseModel


def Param(
    order: int,
    description: str,
    default: str = "",
    *,
    required: bool = True,
    primary: bool = True,
    values_list: Optional[list] = None,
    contains: Optional[list] = None,
    data_type: str = "string",
    allow_list: bool = False,
    **kwargs,
) -> FieldInfo:
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
    :param values_list: To allow the user to choose from a pre-defined list of values
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
    if values_list is None:
        values_list = []
    if contains is None:
        contains = []

    return Field(
        default=default,
        description=description,
        order=order,
        required=required,
        primary=primary,
        values_list=values_list,
        contains=contains,
        data_type=data_type,
        allow_list=allow_list,
        **kwargs,
    )


class Params(BaseModel):
    pass
