from typing import Optional, get_origin, get_args, TypedDict, Any
from collections.abc import Iterator
from typing_extensions import NotRequired
from pydantic import BaseModel, Field

from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult

from soar_sdk.meta.datatypes import as_datatype


class ActionResult(PhantomActionResult):
    def __init__(
        self, status: bool, message: str, param: Optional[dict] = None
    ) -> None:
        super().__init__(param)
        self.set_status(status, message)


class SuccessActionResult(ActionResult):
    def __init__(self, message: str, param: Optional[dict] = None) -> None:
        super().__init__(True, message, param)


class ErrorActionResult(ActionResult):
    def __init__(self, message: str, param: Optional[dict] = None) -> None:
        super().__init__(False, message, param)


class OutputFieldSpecification(TypedDict):
    data_path: str
    data_type: str
    contains: NotRequired[list[str]]
    example_values: NotRequired[list[str]]


def OutputField(
    cef_types: Optional[list[str]] = None, example_values: Optional[list[str]] = None
) -> Any:  # noqa: ANN401
    return Field(
        examples=example_values,
        cef_types=cef_types,
    )


class ActionOutput(BaseModel):
    """
    ActionOutput defines the JSON schema that an action is expected to output.

    It is translated into SOAR datapaths, example values, and CEF fields.
    """

    @classmethod
    def _to_json_schema(
        cls, parent_datapath: str = "action_result.data.*"
    ) -> Iterator[OutputFieldSpecification]:
        """
        Converts the ActionOutput class to a JSON schema.
        """
        for field_name, field in cls.__fields__.items():
            field_type = field.annotation
            datapath = parent_datapath + f".{field_name}"

            # Handle list types, even nested ones
            while get_origin(field_type) is list:
                field_type = get_args(field_type)[0]
                datapath += ".*"

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

            yield schema_field
