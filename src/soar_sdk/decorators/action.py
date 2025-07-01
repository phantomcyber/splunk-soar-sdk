import inspect
from functools import wraps
from typing import Callable, Optional, Any

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult, ActionOutput
from soar_sdk.params import Params
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action, action_protocol
from soar_sdk.exceptions import ActionFailure
from soar_sdk.async_utils import run_async_if_needed
import traceback

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
                result = run_async_if_needed(result)
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
