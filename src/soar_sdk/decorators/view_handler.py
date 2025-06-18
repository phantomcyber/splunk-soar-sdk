import inspect
from functools import wraps
from typing import Callable, Optional, Any

from soar_sdk.action_results import ActionResult
from soar_sdk.views.component_registry import COMPONENT_REGISTRY
from pydantic import BaseModel
from soar_sdk.models.view import ViewContext, AllAppRuns, ResultSummary
from soar_sdk.views.view_parser import ViewFunctionParser
from soar_sdk.views.template_renderer import (
    get_template_renderer,
    get_templates_dir,
    BASE_TEMPLATE_PATH,
)
from soar_sdk.compat import remove_when_soar_newer_than

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soar_sdk.app import App


class ViewHandlerDecorator:
    """
    Class-based decorator for view handler functionality.
    """

    def __init__(self, app: "App", *, template: Optional[str] = None) -> None:
        self.app = app
        self.template = template

    @staticmethod
    def _validate_view_function_signature(
        function: Callable,
        template: Optional[str] = None,
        component_type: Optional[str] = None,
    ) -> None:
        """Validate that the function signature is compatible with view handlers."""
        signature = inspect.signature(function)

        if len(signature.parameters) < 1:
            raise TypeError(
                f"View function {function.__name__} must accept at least 1 parameter"
            )

        if signature.return_annotation == inspect.Signature.empty:
            raise TypeError(
                f"View function {function.__name__} must have a return type annotation"
            )

        # Custom template, handler should return a dict context
        if template:
            if signature.return_annotation is not dict:
                raise TypeError(
                    f"View handler {function.__name__} must return dict, got {signature.return_annotation}"
                )
            return

        # Rendering HTML itself, rare case
        if signature.return_annotation is str:
            return

        # Reusable component, returns one of our component models
        if component_type:
            return

        raise TypeError(
            f"View handler {function.__name__} has invalid return type: {signature.return_annotation}. Handlers must define a template and return a dict, return a predefined view component, or return a fully-rendered HTML string."
        )

    def __call__(self, function: Callable) -> Callable:
        """
        Decorator for custom view functions with output parsing and template rendering.

        The decorated function receives parsed ActionOutput objects and can return either a dict for template rendering, HTML string, or component data model.
        If a template is provided, dict results will be rendered using the template. Component type is automatically inferred from the return type annotation.
        """
        # Infer component type from return annotation
        component_type = COMPONENT_REGISTRY.get(
            inspect.signature(function).return_annotation
        )

        # Validate function signature
        self._validate_view_function_signature(function, self.template, component_type)

        # Wrapper emulates signature that SOAR sends to view handlers
        @wraps(function)
        def view_wrapper(
            action: str,  # Action identifier
            all_app_runs: list[
                tuple[dict[str, Any], list[ActionResult]]
            ],  # Raw app run data
            context: dict[str, Any],  # View context
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> str:
            def handle_html_output(html: str) -> str:
                remove_when_soar_newer_than(
                    "6.4.1", "SOAR now fully supports prerendering views"
                )
                if context.get("accepts_prerender"):
                    context["prerender"] = True
                    return html
                context["html_content"] = html
                return BASE_TEMPLATE_PATH

            def render_with_error_handling(
                render_func: Callable[[], str], error_type: str, target_name: str
            ) -> str:
                try:
                    return handle_html_output(render_func())
                except Exception as e:
                    templates_dir = get_templates_dir(function.__globals__)
                    renderer = get_template_renderer("jinja", templates_dir)
                    error_html = renderer.render_error_template(
                        error_type,
                        f"Failed to render {target_name}: {e!s}",
                        function.__name__,
                        target_name,
                    )
                    return handle_html_output(error_html)

            try:
                parser: ViewFunctionParser = ViewFunctionParser(function)

                # Parse context to ViewContext (coming from app_interface)
                parsed_context = ViewContext.parse_obj(context)

                # Parse all_app_runs to AllAppRuns (coming from app_interface)
                parsed_all_app_runs: AllAppRuns = []
                for app_run_data, action_results in all_app_runs:
                    result_summary = ResultSummary.parse_obj(app_run_data)
                    parsed_all_app_runs.append((result_summary, action_results))

                result = parser.execute(
                    action, parsed_all_app_runs, parsed_context, *args, **kwargs
                )
            except Exception as e:
                templates_dir = get_templates_dir(function.__globals__)
                renderer = get_template_renderer("jinja", templates_dir)
                target = self.template or component_type or "unknown"
                error_type = (
                    "View Function Error"
                    if self.template
                    else "Component Function Error"
                )
                error_html = renderer.render_error_template(
                    error_type,
                    f"Error in {('view' if self.template else 'component')} function '{function.__name__}': {e!s}",
                    function.__name__,
                    target,
                )
                return handle_html_output(error_html)

            # Rendered own HTML
            if isinstance(result, str):
                return handle_html_output(result)

            templates_dir = get_templates_dir(function.__globals__)
            renderer = get_template_renderer("jinja", templates_dir)

            # Reusable component
            if isinstance(result, BaseModel):
                result_dict = result.dict()
                template_name = f"components/{component_type}.html"
                err_msg = "Component Rendering Failed"
                err_context = f"component '{component_type}'"

            # Template rendering
            else:
                result_dict = result
                template_name = self.template or ""
                err_msg = "Template Rendering Failed"
                err_context = f"template '{self.template}'"

            render_context = {**context, **result_dict}
            return render_with_error_handling(
                lambda: renderer.render_template(template_name, render_context),
                err_msg,
                err_context,
            )

        return view_wrapper
