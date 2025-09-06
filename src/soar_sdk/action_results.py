from typing import Optional, Union, get_origin, get_args, Any
from collections.abc import Iterator
from typing_extensions import NotRequired, TypedDict
from pydantic import BaseModel, Field

from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult

from soar_sdk.meta.datatypes import as_datatype

remove_when_soar_newer_than(
    "7.0.0", "NotRequired from typing_extensions is in typing in Python 3.11+"
)


class ActionResult(PhantomActionResult):
    """Use this to simply indicate whether an action succeeded or failed.

    ActionResult also optionally supports attaching an action result message and parameters used by the action. It does not support
    advanced use cases like datapaths, example values and more complex output schemas. For that take a look at ActionOutput.


    Args:
        status: Boolean indicating whether the action succeeded (True) or failed (False).
        message: Descriptive message about the action result, typically explaining
            what happened or why an action failed.
        param: Optional dictionary containing the parameters that were passed to
            the action, useful for debugging and logging.

    Example:
        >>> from soar_sdk.action_results import ActionResult
        >>> @app.action()
        ... def example_action(
        ...     params: Params, soar: SOARClient, asset: Asset
        ... ) -> ActionResult:
        ...     return ActionResult(True, "Successfully executed action")
    """

    def __init__(
        self,
        status: bool,
        message: str,
        param: Optional[dict] = None,
    ) -> None:
        """Initialize an ActionResult with status, message, and optional parameters.

        Args:
            status: Boolean indicating success (True) or failure (False).
            message: Descriptive message about the action outcome.
            param: Optional dictionary of parameters passed to the action.
        """
        super().__init__(param)
        self.set_status(status, message)


class OutputFieldSpecification(TypedDict):
    """Type specification for action output field metadata.

    This TypedDict defines the structure for describing action output fields
    in SOAR. It's used internally to generate JSON schemas and provide metadata about
    the data that actions produce.

    Attributes:
        data_path: The dot-notation path where this field appears in the action
            output data (e.g., "summary.total_objects", "data.*.ip").
        data_type: The expected data type for this field. Common values include
            "string", "numeric", "boolean".
        contains: Optional list of CEF (Common Event Format) field types that
            this field represents (e.g., ["ip", "domain", "hash"]).
        example_values: Optional list of example values that demonstrate what
            this field might contain, used for documentation and testing.

    Example:
        >>> field_spec: OutputFieldSpecification = {
        ...     "data_path": "data.*.ip_address",
        ...     "data_type": "string",
        ...     "contains": ["ip"],
        ...     "example_values": ["192.168.1.1", "10.0.0.1"],
        ... }
    """

    data_path: str
    data_type: str
    contains: NotRequired[list[str]]
    example_values: NotRequired[list[Union[str, float, bool]]]


def OutputField(
    cef_types: Optional[list[str]] = None,
    example_values: Optional[list[Union[str, float, bool]]] = None,
    alias: Optional[str] = None,
) -> Any:  # noqa: ANN401
    """Define metadata for an action output field.

    This function creates field metadata that is used to describe how action
    output fields should look like, including CEF mapping and example values
    for documentation and validation.

    Args:
        cef_types: Optional list of CEF (Common Event Format) field names that
            this output field maps to. Used for integration with SIEM systems.
        example_values: Optional list of example values for this field, used
            in documentation and for testing/validation purposes.
        alias: Optional alternative name for the field when serialized.

    Returns:
        A Pydantic Field object with the specified metadata.

    Example:
        >>> class MyActionOutput(ActionOutput):
        ...     ip_address: str = OutputField(
        ...         cef_types=["sourceAddress", "destinationAddress"],
        ...         example_values=["192.168.1.1", "10.0.0.1"],
        ...     )
        ...     count: int = OutputField(example_values=[1, 5, 10])
    """
    return Field(
        examples=example_values,
        cef_types=cef_types,
        alias=alias,
    )


class ActionOutput(BaseModel):
    """Base class for defining structured action output schemas.

    ActionOutput defines the JSON schema that an action is expected to output.
    It is translated into datapaths, example values, and CEF fields for
    integration with the SOAR platform.

    Subclasses should define fields using type annotations and OutputField()
    for metadata. The schema is automatically converted to SOAR-compatible
    format for manifest generation and data validation.

    Example:
        >>> class MyActionOutput(ActionOutput):
        ...     hostname: str = OutputField(
        ...         cef_types=["destinationHostName"],
        ...         example_values=["server1.example.com"],
        ...     )
        ...     port: int = OutputField(example_values=[80, 443, 8080])
        ...     is_secure: bool  # Automatically gets True/False examples
        ...
        ...     under_field: str = OutputField(
        ...         alias="_under_field"
        ...     )  # Model fields can't start with an underscore, so we're using an alias to create the proper JSON key

    Note:
        Fields cannot be Union or Optional types. Use specific types only.
        Nested ActionOutput classes are supported for complex data structures.
    """

    def generate_action_summary_message(self) -> str:
        """.. deprecated:: 1.3.0

        Generate a summary message for the action output.

        This method provides a human-readable summary of the action results,
        which appears when running the action in a SOAR playbook or container.

        Returns:
            A string summarizing the action output.

        """
        return "Action completed successfully."

    @classmethod
    def _to_json_schema(
        cls, parent_datapath: str = "action_result.data.*"
    ) -> Iterator[OutputFieldSpecification]:
        """Convert the ActionOutput class to SOAR-compatible JSON schema.

        This method analyzes the class fields and their types to generate
        OutputFieldSpecification objects that describe the data structure
        for SOAR's manifest and data processing systems.

        Args:
            parent_datapath: The base datapath for fields in this output.
                Defaults to "action_result.data.*" for top-level outputs.

        Yields:
            OutputFieldSpecification objects describing each field in the schema.

        Raises:
            TypeError: If a field type cannot be serialized, is Union/Optional,
                or if a nested ActionOutput type is encountered incorrectly.

        Note:
            List types are automatically handled with ".*" datapath suffixes.
            Nested ActionOutput classes are recursively processed.
            Boolean fields automatically get [True, False] example values.
        """
        for _field_name, field in cls.__fields__.items():
            field_name = alias if (alias := field.alias) else _field_name

            field_type = field.annotation
            datapath = parent_datapath + f".{field_name}"

            # Handle list types, even nested ones
            while get_origin(field_type) is list:
                field_type = get_args(field_type)[0]
                datapath += ".*"

            # For some reason, issubclass(Optional, _) doesn't work.
            # This provides a nicer error message to an app dev, unless and
            # until we can build proper support for Optional types.
            if get_origin(field_type) is Union:
                raise TypeError(
                    f"Output field {field_name} cannot be Union or Optional."
                )

            if issubclass(field_type, ActionOutput):
                # If the field is another ActionOutput, recursively call _to_json_schema
                yield from field_type._to_json_schema(datapath)
                continue
            else:
                try:
                    type_name = as_datatype(field_type)
                except TypeError as e:
                    raise TypeError(
                        f"Failed to serialize output field {field_name}: {e}"
                    ) from None

            schema_field = OutputFieldSpecification(
                data_path=datapath, data_type=type_name
            )

            if cef_types := field.field_info.extra.get("cef_types"):
                schema_field["contains"] = cef_types
            if examples := field.field_info.extra.get("examples"):
                schema_field["example_values"] = examples

            if field_type is bool:
                schema_field["example_values"] = [True, False]

            yield schema_field


class GenericActionOutput(ActionOutput):
    """Output class for generic actions.

    This class extends the `ActionOutput` class and adds a status_code and response_body field. You can use this class as is or extend it to add more fields.

    Example:
        >>> class CustomGenericActionOutput(GenericActionOutput):
        ...     error: str = OutputField(example_values=["Invalid credentials"])

    Note:
        The status_code field is used to return the HTTP status code of the response.
        The response_body field is used to return the response body of the response.
    """

    status_code: int = OutputField(example_values=[200, 404, 500])
    response_body: str = OutputField(example_values=['{"key": "value"}'])
