import types
from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin


def parse_json_schema_extra(json_schema_extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract json_schema_extra as a dict, handling both dict and callable forms."""
    if callable(json_schema_extra):
        return {}
    return json_schema_extra or {}


@dataclass(frozen=True)
class NormalizedFieldType:
    """Normalized field annotation details."""

    base_type: type
    list_depth: int
    is_optional: bool


def normalize_field_annotation(
    annotation: Any,  # noqa: ANN401
    *,
    field_name: str,
    context: str,
    allow_list: bool,
) -> NormalizedFieldType:
    """Normalize an annotation by unwrapping Optional and list types.

    Args:
        annotation: The field annotation to normalize.
        field_name: Name of the field for error reporting.
        context: Context string for error reporting (e.g., "parameter").
        allow_list: Whether list types are allowed.

    Returns:
        NormalizedFieldType describing the base type, list nesting, and optionality.

    Raises:
        TypeError: If unsupported unions or list shapes are encountered.
    """
    list_depth = 0
    is_optional = False

    while True:
        origin = get_origin(annotation)
        if origin is list:
            type_args = get_args(annotation)
            if len(type_args) != 1:
                raise TypeError(
                    f"{context} field {field_name} is invalid: list types must have exactly one type argument."
                )
            list_depth += 1
            annotation = type_args[0]
            continue

        if origin in (types.UnionType, Union):
            # types.UnionType is for `X | Y` (Python 3.10+)
            type_args = tuple(
                arg for arg in get_args(annotation) if arg is not type(None)
            )
            if len(type_args) != 1:
                raise TypeError(
                    f"{context} field {field_name} is invalid: only Optional[T] is supported for unions."
                )
            is_optional = True
            annotation = type_args[0]
            continue

        break

    if list_depth and not allow_list:
        raise TypeError(
            f"{context} field {field_name} is invalid: list types are not supported."
        )

    if not isinstance(annotation, type):
        raise TypeError(
            f"{context} field {field_name} has invalid type annotation: {annotation}"
        )

    return NormalizedFieldType(
        base_type=annotation, list_depth=list_depth, is_optional=is_optional
    )


def resolve_required(json_schema_extra: dict[str, Any], is_optional: bool) -> bool:
    """Resolve required flag using JSON schema metadata and optionality."""
    if "required" in json_schema_extra:
        return bool(json_schema_extra.get("required"))
    return not is_optional
