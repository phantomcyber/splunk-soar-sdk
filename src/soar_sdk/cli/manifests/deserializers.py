import dataclasses
import json
from pathlib import Path
from typing import Any, NamedTuple, Optional, TypeVar, Union, cast
import pydantic

from soar_sdk.action_results import ActionOutput, OutputFieldSpecification, OutputField
from soar_sdk.cli.utils import normalize_field_name, NormalizationResult
from soar_sdk.compat import PythonVersion
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.meta.app import AppMeta
from soar_sdk.params import Params, Param
from soar_sdk.meta.datatypes import to_python_type


class DeserializedAppMeta(NamedTuple):
    app_meta: AppMeta
    actions_with_custom_views: list[str]
    has_rest_handlers: bool
    has_webhooks: bool


class AppMetaDeserializer:
    @staticmethod
    def from_app_json(json_path: Path) -> DeserializedAppMeta:
        manifest: dict[str, Any] = json.loads(json_path.read_text())

        # Massage the python_version field, which may be a comma-separated string
        python_version = manifest.pop("python_version", None)
        if isinstance(python_version, str):
            manifest["python_version"] = PythonVersion.from_csv(python_version)
        elif isinstance(python_version, list):
            manifest["python_version"] = [
                PythonVersion.from_str(py) for py in python_version
            ]

        deserialized_actions = [
            ActionDeserializer.from_action_json(action)
            for action in manifest.get("actions", [])
            if isinstance(action, dict)
        ]

        manifest["actions"] = [action.action_meta for action in deserialized_actions]
        actions_with_custom_views = [
            action.action_meta.identifier
            for action in deserialized_actions
            if action.has_custom_view
        ]
        app_meta = AppMeta(project_name=json_path.parent.name, **manifest)

        has_rest_handlers = isinstance(manifest.get("rest_handler"), str)
        has_webhooks = isinstance(manifest.get("webhooks"), dict)

        return DeserializedAppMeta(
            app_meta=app_meta,
            actions_with_custom_views=actions_with_custom_views,
            has_rest_handlers=has_rest_handlers,
            has_webhooks=has_webhooks,
        )


class FieldSpec(NamedTuple):
    type_: type
    default: Any


@dataclasses.dataclass
class OutputFieldModel:
    data_path: str
    data_type: str
    contains: Optional[list[str]] = None
    example_values: Optional[list[Union[str, float, bool]]] = None
    column_name: Optional[str] = None
    column_order: Optional[int] = None


class DeserializedActionMeta(NamedTuple):
    action_meta: ActionMeta
    has_custom_view: bool


class ActionDeserializer:
    @classmethod
    def from_action_json(cls, action: dict[str, Any]) -> DeserializedActionMeta:
        action["parameters"] = cls.parse_parameters(
            action["action"], action.get("parameters", {})
        )
        action["output"] = cls.parse_output(action["action"], action.get("output", []))
        return DeserializedActionMeta(
            action_meta=ActionMeta.parse_obj(action),
            has_custom_view=action.get("render", {}).get("type") == "custom",
        )

    @classmethod
    def parse_parameters(
        cls, action_name: str, parameters: dict[str, Any]
    ) -> type[Params]:
        """
        Parses the parameters from a dictionary to generate a Params model class
        """
        # If no parameters, return base Params class
        if not parameters:
            return Params

        # Create field definitions for each parameter
        fields: dict[str, FieldSpec] = {}
        for param_name, param_spec in parameters.items():
            if param_spec["data_type"].startswith("ph"):
                # Skip parameters that are placeholders
                continue
            fields[param_name] = cls._create_param_field(param_spec)

        # Dynamically create a subclass of Params
        action_name = cls._clean_action_name(action_name).normalized
        return pydantic.create_model(
            f"{action_name}Params",
            __base__=Params,
            **(
                cast(dict[str, Any], fields)
            ),  # our type hints are more precise than pydantic's
        )

    @staticmethod
    def _create_param_field(param_spec: dict[str, Any]) -> FieldSpec:
        """
        Create a parameter field from a parameter specification.
        """
        # Get the Python type from data_type
        data_type = param_spec.get("data_type", "string")
        python_type = to_python_type(data_type)

        # Create Param field with all the metadata
        param_field = Param(
            description=param_spec.get("description"),
            required=param_spec.get("required", True),
            primary=param_spec.get("primary", False),
            default=param_spec.get("default"),
            value_list=param_spec.get("value_list"),
            cef_types=param_spec.get("contains"),  # 'contains' maps to 'cef_types'
            allow_list=param_spec.get("allow_list", False),
            sensitive=(data_type == "password"),
        )

        return FieldSpec(python_type, param_field)

    @classmethod
    def parse_output(
        cls, action_name: str, output: list[OutputFieldSpecification]
    ) -> type[ActionOutput]:
        """
        Parses the output from a list of OutputFieldSpecification to generate an ActionOutput model class
        """
        # Filter out automatic fields and extract the action's real output fields
        output_fields = cls._filter_output_fields(output)

        # If no interesting output, return base ActionOutput class
        if not output_fields:
            return ActionOutput

        # Build a map from datapath to spec, ensuring no duplicates and preparing for nested structure
        fields_by_datapath: dict[str, OutputFieldModel] = {}
        for field_spec in output_fields:
            if field_spec["data_path"] in fields_by_datapath:
                raise ValueError(
                    f"Duplicate output field data path: action_result.data.*.{field_spec['data_path']}"
                )
            fields_by_datapath[field_spec["data_path"]] = OutputFieldModel(**field_spec)

        output_structure = cls._build_output_structure(fields_by_datapath)
        return cls._build_output_class(action_name, output_structure)

    @staticmethod
    def _build_output_structure(
        datapath_specs: dict[str, OutputFieldModel],
    ) -> dict[str, Union[list, dict, OutputFieldModel]]:
        """
        Parse a datapath string into a dictionary.

        Args:
            datapath_specs: The set of datapaths and their types to parse.

        Returns:
            dict: A dictionary representing the blown-up data structure of the datapaths, where the leaf values are their specifications
        """

        def set_nested_value(
            field_struct: dict[str, Union[list, dict, OutputFieldModel]],
            path_parts: list[str],
            field_spec: OutputFieldModel,
        ) -> Union[list, dict, OutputFieldModel]:
            """Recursively set a field spec in the nested output field structure."""
            # Base case: we're at a leaf node and can return the field spec directly
            if not path_parts:
                return field_spec

            current_key = path_parts.pop(0)

            # Recursive case: this portion of the datapath is a list (indicated by '*')
            if current_key == "*":
                return [set_nested_value({}, path_parts, field_spec)]

            # Recursive case: this portion of the datapath is an object key
            next_field_struct = cast(
                dict[str, Union[list, dict, OutputFieldModel]],
                field_struct.get(current_key, {}),
            )
            field_struct[current_key] = set_nested_value(
                next_field_struct, path_parts, field_spec
            )
            return field_struct

        MergeT = TypeVar("MergeT", bound=Union[list, dict, OutputFieldModel])

        def merge(base: MergeT, new_structure: MergeT) -> MergeT:
            """Merge two nested structures, handling arrays and objects."""
            if isinstance(new_structure, list) and isinstance(base, list):
                # Both are arrays - merge their first elements
                # These shouldn't be empty, hence the pragmas, but we handle them gracefully
                if not base:  # pragma: no cover
                    # mypy is bad at inferring types in this case
                    return new_structure  # type: ignore[return-value]
                if not new_structure:  # pragma: no cover
                    # mypy is bad at inferring types in this case
                    return base  # type: ignore[return-value]
                # Typing isn't smart enough to infer this known truth, so we cast
                return cast(MergeT, [merge(base[0], new_structure[0])])

            if isinstance(new_structure, dict) and isinstance(base, dict):
                # Both are objects - merge recursively
                result = base.copy()
                for key, value in new_structure.items():
                    if key in result:
                        result[key] = merge(result[key], value)
                    else:
                        result[key] = value

                # Typing isn't smart enough to infer this known truth, so we cast
                return cast(MergeT, result)

            # One is OutputFieldModel or they're different types - new takes precedence
            # Should never happen in reality, hence the pragma, but we handle it gracefully
            return new_structure  # pragma: no cover

        result: dict[str, Union[list, dict, OutputFieldModel]] = {}

        for datapath, field_spec in datapath_specs.items():
            path_parts = datapath.split(".")
            nested_structure = cast(
                dict[str, Union[list, dict, OutputFieldModel]],
                set_nested_value({}, path_parts, field_spec),
            )
            merged = merge(result, nested_structure)
            # Since we start with an empty dict and merge should preserve that at top level
            result = merged if isinstance(merged, dict) else {}

        return result

    @classmethod
    def _build_output_class(
        cls,
        action_name: str,
        output_structure: dict[str, Union[dict, list, OutputFieldModel]],
    ) -> type[ActionOutput]:
        """
        Recursively (depth-first) build dynamic pydantic models for the action output,
        from the output data paths definitions.

        Returns:
            A dynamically created ActionOutput class with nested structure based on the output fields.
        """
        fields: dict[str, FieldSpec] = {}
        for field_name, field_struct in output_structure.items():
            normalized_name, field_spec = cls._build_output_field(
                field_name, field_struct
            )
            fields[normalized_name] = field_spec

        return pydantic.create_model(
            f"{cls._clean_action_name(action_name).normalized}Output",
            __base__=ActionOutput,
            **(cast(dict[str, Any], fields)),
        )

    @classmethod
    def _build_output_field(
        cls, field_name: str, output_structure: Union[list, dict, OutputFieldModel]
    ) -> tuple[str, FieldSpec]:
        normalized_name = normalize_field_name(field_name)

        # Base case: primitive (leaf node) output field
        if isinstance(output_structure, OutputFieldModel):
            py_type = to_python_type(output_structure.data_type)
            return normalized_name.normalized, FieldSpec(
                py_type,
                OutputField(
                    cef_types=output_structure.contains,
                    example_values=output_structure.example_values,
                    alias=normalized_name.original
                    if normalized_name.modified
                    else None,
                ),
            )

        # Recursive case: list node
        if isinstance(output_structure, list):
            # By convention, a list output structure should contain exactly one item.
            if len(output_structure) != 1:  # pragma: no cover
                raise ValueError(
                    f"List output structure for field '{field_name}' must contain exactly one item, got {len(output_structure)}"
                )
            output_spec = output_structure.pop()
            field_name, field_spec = cls._build_output_field(field_name, output_spec)
            field_type = (
                field_spec.type_
            )  # this helps mypy, but it's still not quite happy
            return field_name, FieldSpec(
                type_=list[field_type],  # type: ignore[valid-type]
                default=field_spec.default,
            )

        # Recursive case: object node
        if isinstance(output_structure, dict):
            model = cls._build_output_class(field_name, output_structure)
            return normalized_name.normalized, FieldSpec(model, ...)

        raise TypeError(  # pragma: no cover
            f"Unexpected output structure type: {type(output_structure)} for field '{field_name}'"
        )

    @staticmethod
    def _filter_output_fields(
        output: list[OutputFieldSpecification],
    ) -> list[OutputFieldSpecification]:
        """
        Filter out automatic fields and extract the action's real output fields.
        """
        output_fields: list[OutputFieldSpecification] = []
        for output_spec in output:
            data_path = output_spec["data_path"].removeprefix("action_result.")

            # Only process data.* fields
            if data_path.startswith("data.*."):
                data_path = data_path.removeprefix("data.*.")
                output_fields.append({**output_spec, "data_path": data_path})

            # Implicitly skips the automatic output fields;
            # like parameter, status, message, and summary

        return output_fields

    @staticmethod
    def _clean_action_name(action_name: str) -> NormalizationResult:
        """Clean action name for use in class names."""
        return normalize_field_name(
            action_name.title().replace(" ", "").replace("_", "")
        )
