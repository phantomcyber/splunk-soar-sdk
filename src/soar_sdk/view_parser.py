from typing import (
    Any,
    Callable,
    TypeVar,
    Union,
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
        self,
        function: Callable,
    ) -> None:
        self.function = function

        # Auto-detect output class from function signature
        detected_class = self.auto_detect_output_class(function)
        self.output_class: type[T] = cast(type[T], detected_class)

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

    def parse_action_results(
        self, raw_all_app_runs: list[tuple[Any, list[ActionResult]]]
    ) -> tuple[list[T], list[tuple[AppRunMetadata, list[ActionResult]]]]:
        parsed_outputs: list[T] = []
        parsed_app_runs: list[tuple[AppRunMetadata, list[ActionResult]]] = []

        for app_run_metadata, action_results in raw_all_app_runs:
            if isinstance(app_run_metadata, dict):
                if app_run_metadata:
                    parsed_metadata: AppRunMetadata = AppRunMetadata.parse_obj(
                        app_run_metadata
                    )
                else:
                    parsed_metadata = AppRunMetadata()
            else:
                parsed_metadata = app_run_metadata

            parsed_app_runs.append((parsed_metadata, action_results))

            # Extract and parse outputs from each result
            for result in action_results:
                for data_item in result.get_data():
                    try:
                        parsed_output = self.output_class.parse_obj(data_item)
                        parsed_outputs.append(parsed_output)
                    except Exception as e:
                        output_class_name = self.output_class.__name__
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
        else:
            result = self.function(context, action, parsed_outputs, *args[3:], **kwargs)

        # Update context
        if isinstance(result, str) and isinstance(context, ViewContext):
            context.html_content = result

        return result
