from typing import (
    Any,
    Callable,
    TypeVar,
    Union,
    Optional,
    get_origin,
    get_args,
    Generic,
    cast,
)
import contextlib
import inspect
from soar_sdk.action_results import ActionOutput, ActionResult
from soar_sdk.models.view import ViewContext, AppRunMetadata

T = TypeVar("T", bound=ActionOutput)


AllAppRuns = list[tuple[AppRunMetadata, list[ActionResult]]]


class ViewFunctionParser(Generic[T]):
    """Handles parsing and validation of view function signatures and execution."""

    def __init__(
        self, function: Callable, output_class: Optional[type[T]] = None
    ) -> None:
        self.function = function

        # Auto-detect output class if not provided
        if output_class is None:
            detected_class = self.auto_detect_output_class(function)
            output_class = cast(type[T], detected_class)

        self.output_class: Optional[type[T]] = output_class

        # Validate function signature
        self.validate_function_signature(function)

    @staticmethod
    def auto_detect_output_class(function: Callable) -> type[ActionOutput]:
        """Auto-detect ActionOutput class from function type annotations."""
        signature = inspect.signature(function)

        for param in signature.parameters.values():
            if param.annotation == inspect.Parameter.empty:
                continue

            origin = get_origin(param.annotation)
            if origin is list:
                args = get_args(param.annotation)
                if args and issubclass(args[0], ActionOutput):
                    return args[0]
            elif isinstance(param.annotation, type) and issubclass(
                param.annotation, ActionOutput
            ):
                return param.annotation

        raise TypeError(
            f"Could not auto-detect ActionOutput class from function signature of {function.__name__}."
        )

    @staticmethod
    def validate_function_signature(function: Callable) -> None:
        """Validate that the function signature is compatible with view parsing."""
        signature = inspect.signature(function)

        if len(signature.parameters) < 1:
            raise TypeError(
                f"View function {function.__name__} must accept at least 1 parameter"
            )

        if (
            signature.return_annotation != inspect.Parameter.empty
            and signature.return_annotation not in [str, dict, dict[str, Any]]
        ):
            raise TypeError(
                f"View function {function.__name__} must return str or dict"
            )

    def _extract_data_from_result(self, result: ActionResult) -> list[dict]:
        data_items = []

        data = result.get_data()

        if isinstance(data, list):
            data_items.extend([item for item in data if isinstance(item, dict)])
        elif isinstance(data, dict):
            data_items.append(data)

        return data_items

    def parse_action_results(
        self, raw_all_app_runs: list[tuple[Any, list[ActionResult]]]
    ) -> tuple[list[T], list[tuple[AppRunMetadata, list[ActionResult]]]]:
        parsed_outputs: list[T] = []
        parsed_app_runs: list[tuple[AppRunMetadata, list[ActionResult]]] = []

        for app_run_metadata, action_results in raw_all_app_runs:
            if isinstance(app_run_metadata, dict):
                try:
                    parsed_metadata: AppRunMetadata = AppRunMetadata.parse_obj(
                        app_run_metadata
                    )
                except Exception:
                    # If parsing fails, create a fallback AppRunMetadata object
                    parsed_metadata = (
                        AppRunMetadata(**app_run_metadata)
                        if app_run_metadata
                        else AppRunMetadata()
                    )
            else:
                parsed_metadata = app_run_metadata

            parsed_app_runs.append((parsed_metadata, action_results))

            # Extract and parse outputs from each result
            for result in action_results:
                for data_item in self._extract_data_from_result(result):
                    try:
                        if self.output_class is not None:
                            parsed_output = self.output_class.parse_obj(data_item)
                            parsed_outputs.append(parsed_output)
                    except Exception as e:
                        output_class_name = (
                            self.output_class.__name__
                            if self.output_class
                            else "Unknown"
                        )
                        raise ValueError(
                            f"Data parsing failed for {output_class_name}: {e}"
                        ) from e

        return parsed_outputs, parsed_app_runs

    def execute(self, *args: object, **kwargs: object) -> Union[str, dict]:
        if len(args) < 3:
            return self.function(*args, **kwargs)

        action, raw_all_app_runs, raw_context = args[0], args[1], args[2]

        # Parse context
        context = raw_context
        if isinstance(raw_context, dict):
            with contextlib.suppress(Exception):
                context = ViewContext.parse_obj(raw_context)

        # Parse outputs
        if not isinstance(raw_all_app_runs, list):
            raise TypeError("Expected raw_all_app_runs to be a list")
        parsed_outputs, parsed_app_runs = self.parse_action_results(raw_all_app_runs)

        # Execute
        sig = inspect.signature(self.function)
        param_count = len(sig.parameters)

        if param_count == 1:
            result = self.function(parsed_outputs, **kwargs)
        elif param_count == 2:
            result = self.function(context, parsed_outputs, **kwargs)
        elif param_count == 3:
            result = self.function(context, action, parsed_outputs, **kwargs)
        else:
            result = self.function(
                context, action, parsed_outputs, parsed_app_runs, *args[4:], **kwargs
            )

        # Update context
        if isinstance(result, str) and isinstance(context, ViewContext):
            context.html_content = result

        return result
