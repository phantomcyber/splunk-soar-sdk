import inspect
from functools import wraps
from typing import Callable, Optional, Any

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult, ActionOutput
from soar_sdk.params import Params
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action, action_protocol
from soar_sdk.exceptions import ActionFailure
import traceback
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


class ActionDecorator:
    """
    Class-based decorator for action functionality.
    """

    def __init__(
        self,
        app: "App",
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        description: Optional[str] = None,
        verbose: str = "",
        action_type: str = "generic",
        read_only: bool = True,
        params_class: Optional[type[Params]] = None,
        output_class: Optional[type[ActionOutput]] = None,
        view_handler: Optional[Callable] = None,
        versions: str = "EQ(*)",
    ) -> None:
        self.app = app
        self.name = name
        self.identifier = identifier
        self.description = description
        self.verbose = verbose
        self.action_type = action_type
        self.read_only = read_only
        self.params_class = params_class
        self.output_class = output_class
        self.view_handler = view_handler
        self.versions = versions

    def __call__(self, function: Callable) -> Action:
        """
        Decorator for the action handling function. Adds the specific meta
        information to the action passed to the generator. Validates types used on
        the action arguments and adapts output for fast and seamless development.
        """
        action_identifier = self.identifier or function.__name__
        if action_identifier == "test_connectivity":
            raise TypeError(
                "The 'test_connectivity' action identifier is reserved and cannot be used. Please use the test_connectivity decorator instead."
            )
        if self.app.actions_manager.get_action(action_identifier):
            raise TypeError(
                f"Action identifier '{action_identifier}' is already used. Please use a different identifier."
            )

        action_name = self.name or str(action_identifier.replace("_", " "))

        spec = inspect.getfullargspec(function)
        validated_params_class = self.app._validate_params_class(
            action_name, spec, self.params_class
        )

        return_type = inspect.signature(function).return_annotation
        if return_type is not inspect.Signature.empty:
            validated_output_class = return_type
        elif self.output_class is not None:
            validated_output_class = self.output_class
        else:
            raise TypeError(
                "Action function must specify a return type via type hint or output_class parameter"
            )

        if not issubclass(validated_output_class, ActionOutput):
            raise TypeError(
                "Return type for action function must be derived from ActionOutput class."
            )

        @action_protocol
        @wraps(function)
        def inner(
            params: Params,
            /,
            soar: SOARClient = self.app.soar_client,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> bool:
            """
            Validates input params and adapts the results from the action.
            """
            action_params = self.app._validate_params(params, action_name)
            kwargs = self.app._build_magic_args(function, soar=soar, **kwargs)

            try:
                result = function(action_params, *args, **kwargs)
            except ActionFailure as e:
                e.set_action_name(action_name)
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=str(e)),
                    self.app.actions_manager,
                )
            except Exception as e:
                self.app.actions_manager.add_exception(e)
                traceback_str = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=traceback_str),
                    self.app.actions_manager,
                )

            return self.app._adapt_action_result(
                result, self.app.actions_manager, action_params
            )

        # setting up meta information for the decorated function
        inner.params_class = validated_params_class
        inner.meta = ActionMeta(
            action=action_name,
            identifier=self.identifier or function.__name__,
            description=self.description or inspect.getdoc(function) or action_name,
            verbose=self.verbose,
            type=self.action_type,
            read_only=self.read_only,
            parameters=validated_params_class,
            output=validated_output_class,
            versions=self.versions,
            view_handler=self.view_handler,
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app._dev_skip_in_pytest(function, inner)

        return inner


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


class TestConnectivityDecorator:
    """
    Class-based decorator for test connectivity functionality.
    """

    def __init__(self, app: "App") -> None:
        self.app = app

    def __call__(self, function: Callable) -> Action:
        """
        Decorator for the test connectivity function. Makes sure that only 1 function
        in the app is decorated with this decorator and attaches generic metadata to the
        action. Validates that the only param passed is the SOARClient and adapts the return
        value based on the success or failure of test connectivity.
        """
        if self.app.actions_manager.get_action("test_connectivity"):
            raise TypeError(
                "The 'test_connectivity' decorator can only be used once per App instance."
            )

        signature = inspect.signature(function)
        if signature.return_annotation not in (None, inspect._empty):
            raise TypeError(
                "Test connectivity function must not return any value (return type should be None)."
            )

        action_identifier = "test_connectivity"
        action_name = "test connectivity"

        @action_protocol
        @wraps(function)
        def inner(
            _param: Optional[dict] = None,
            soar: SOARClient = self.app.soar_client,
        ) -> bool:
            kwargs = self.app._build_magic_args(function, soar=soar)

            try:
                result = function(**kwargs)
                if result is not None:
                    raise RuntimeError(
                        "Test connectivity function must not return any value (return type should be None)."
                    )
            except ActionFailure as e:
                e.set_action_name(action_name)
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=str(e)),
                    self.app.actions_manager,
                )
            except Exception as e:
                self.app.actions_manager.add_exception(e)
                traceback_str = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=traceback_str),
                    self.app.actions_manager,
                )

            return self.app._adapt_action_result(
                ActionResult(status=True, message="Test connectivity successful"),
                self.app.actions_manager,
            )

        inner.params_class = None
        inner.meta = ActionMeta(
            action=action_name,
            identifier=action_identifier,
            description=inspect.getdoc(function) or action_name,
            verbose="Basic test for app.",
            type="test",
            read_only=True,
            versions="EQ(*)",
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app._dev_skip_in_pytest(function, inner)
        return inner
