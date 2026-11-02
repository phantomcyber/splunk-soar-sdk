__lazy_modules__ = {
    "inspect",
    "pydantic",
    "soar_sdk.action_results",
    "soar_sdk.async_utils",
    "soar_sdk.models.view",
    "soar_sdk.types",
    "typing",
}

import inspect
from typing import (
    Any,
    Generic,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

from pydantic import BaseModel, TypeAdapter

from soar_sdk.action_results import ActionOutput
from soar_sdk.async_utils import run_async_if_needed
from soar_sdk.models.view import AllAppRuns, ViewContext
from soar_sdk.types import NamedCallable

T = TypeVar("T", bound=ActionOutput)


class ViewFunctionParser(Generic[T]):
    """Handles parsing and validation of view function signatures and execution."""

    def __init__(
        self,
        function: NamedCallable,
    ) -> None:
        self.function = function

        # Auto-detect output class from function signature
        self._output_parameter, detected_class = self._detect_output_parameter(function)
        self.output_class: type[T] = cast(type[T], detected_class)

    @staticmethod
    def auto_detect_output_class(function: NamedCallable) -> type[ActionOutput]:
        """Auto-detect ActionOutput class from function type annotations."""
        return ViewFunctionParser._detect_output_parameter(function)[1]

    @staticmethod
    def _detect_output_parameter(
        function: NamedCallable,
    ) -> tuple[inspect.Parameter, type[ActionOutput]]:
        """Find the output argument, allowing legacy names params and summary."""
        signature = inspect.signature(function)
        parameters = list(signature.parameters.values())
        candidates = [p for p in parameters if p.name not in ("params", "summary")]
        candidates.extend(
            p
            for p in parameters
            if p.name in ("params", "summary")
            and p.kind != inspect.Parameter.KEYWORD_ONLY
        )
        for param in candidates:
            if param.annotation == inspect.Parameter.empty:
                continue

            if get_origin(param.annotation) is list:
                args = get_args(param.annotation)
                if args and issubclass(args[0], ActionOutput):
                    return param, args[0]
            elif isinstance(param.annotation, type) and issubclass(
                param.annotation, ActionOutput
            ):
                return param, param.annotation

        raise TypeError(
            f"Could not auto-detect ActionOutput class from function signature of {function.__name__}."
        )

    def parse_action_results(self, all_app_runs: AllAppRuns) -> list[T]:
        """Given a list of AppRun data in JSON, return a list of ActionOutput models.

        The specific subclass of ActionOutput that is used for parsing is determined by
        the type hints of the function given to the ViewFunctionParser at init time.
        """
        parsed_outputs: list[T] = []

        for app_run_data in all_app_runs:
            # Extract action_results from the app_run_data
            _, action_results = app_run_data

            # Extract and parse outputs from each result
            for result in action_results:
                for data_item in result.get_data():
                    try:
                        parsed_output = self.output_class.model_validate(data_item)
                        parsed_outputs.append(parsed_output)
                    except Exception as e:
                        output_class_name = self.output_class.__name__
                        raise ValueError(
                            f"Data parsing failed for {output_class_name}: {e}"
                        ) from e

        return parsed_outputs

    @staticmethod
    def _parse_metadata(
        all_app_runs: AllAppRuns, parameter: inspect.Parameter
    ) -> list[Any]:
        """Align requested parameters or summaries with the flattened output rows."""
        getter = "get_param" if parameter.name == "params" else "get_summary"
        values = []
        for _, action_results in all_app_runs:
            for result in action_results:
                values.extend([getattr(result, getter)()] * len(result.get_data()))

        if parameter.annotation != inspect.Parameter.empty:
            return TypeAdapter(parameter.annotation).validate_python(values)
        return values

    def execute(
        self,
        action: str,
        raw_all_app_runs: AllAppRuns,
        context: ViewContext,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> str | dict | BaseModel:
        """Wrapper around the object's view function which massages platform inputs as necessary.

        Takes the JSON list of AppRun results provided by Splunk SOAR, parses that into
        the appropriate list of Pydantic models for the specific view handler, and executes
        that view handler (either sync or async depending on the handler's signature).
        """
        # Parse outputs
        parsed_outputs = self.parse_action_results(raw_all_app_runs)

        # Execute
        sig = inspect.signature(self.function)
        magic_parameters = {
            name: parameter
            for name, parameter in sig.parameters.items()
            if name in ("params", "summary")
            and name != self._output_parameter.name
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        }
        magic_arguments = {}
        for name, parameter in magic_parameters.items():
            kwargs.pop(name, None)
            magic_arguments[name] = self._parse_metadata(raw_all_app_runs, parameter)
        legacy_signature = sig.replace(
            parameters=[
                p for p in sig.parameters.values() if p.name not in magic_parameters
            ]
        )
        param_count = len(legacy_signature.parameters)

        if param_count == 1:
            positional_arguments = (parsed_outputs,)
        elif param_count == 2:
            positional_arguments = (context, parsed_outputs)
        else:
            positional_arguments = (context, action, parsed_outputs, *args)

        bound = legacy_signature.bind(*positional_arguments, **kwargs)
        bound.arguments.update(magic_arguments)
        call = inspect.BoundArguments(sig, bound.arguments)
        result = self.function(*call.args, **call.kwargs)

        return run_async_if_needed(result)
