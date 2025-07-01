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
import inspect
from pydantic import BaseModel
from soar_sdk.action_results import ActionOutput
from soar_sdk.models.view import ViewContext, AllAppRuns
from soar_sdk.async_utils import run_async_if_needed

T = TypeVar("T", bound=ActionOutput)


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

            if get_origin(param.annotation) is list:
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

    def parse_action_results(self, all_app_runs: AllAppRuns) -> list[T]:
        parsed_outputs: list[T] = []

        for app_run_data in all_app_runs:
            # Extract action_results from the app_run_data
            _, action_results = app_run_data

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

        return parsed_outputs

    def execute(
        self,
        action: str,
        raw_all_app_runs: AllAppRuns,
        context: ViewContext,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Union[str, dict, BaseModel]:
        # Parse outputs
        parsed_outputs = self.parse_action_results(raw_all_app_runs)

        # Execute
        sig = inspect.signature(self.function)
        param_count = len(sig.parameters)

        if param_count == 1:
            result = self.function(parsed_outputs, **kwargs)
        elif param_count == 2:
            result = self.function(context, parsed_outputs, **kwargs)
        else:
            result = self.function(context, action, parsed_outputs, *args, **kwargs)

        return run_async_if_needed(result)
