import inspect

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.params import GenericActionParams
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.action_results import ActionOutput, GenericActionOutput
from soar_sdk.types import Action, action_protocol
from soar_sdk.exceptions import ActionFailure
from soar_sdk.async_utils import run_async_if_needed
from soar_sdk.logging import getLogger
from functools import wraps
import traceback

from typing import TYPE_CHECKING, Callable, Any, Optional

if TYPE_CHECKING:
    from soar_sdk.app import App


class GenericActionDecorator:
    """
    Class-based decorator for generic action functionality.
    """

    def __init__(
        self,
        app: "App",
        output_class: Optional[type[ActionOutput]] = None,
    ) -> None:
        self.app = app
        self.output_class = output_class

    def __call__(self, function: Callable) -> Action:
        """
        Decorator for the generic action.

        The decorated function implements a generic action that can be used to call any endpoint of the underlying API service this app implements.

        Usage:
        This decorated function automatically gets all the parameters from the GenericActionParams class and passes them to the function. GenericActionParams represents the parameters required for most http requests.
        You should use your existing asset interface to make this request.
        """

        if self.app.actions_manager.get_action("generic_action"):
            raise TypeError(
                "The 'generic_action' decorator can only be used once per App instance."
            )

        # Validate function signature - must have at least one parameter of type GenericActionParams
        signature = inspect.signature(function)
        params = list(signature.parameters.values())

        if not any(param.annotation == GenericActionParams for param in params):
            raise TypeError(
                f"Generic action function must have at least one parameter of type GenericActionParams, got {params[0].annotation}"
            )

        action_identifier = "generic_action"
        action_name = "generic action"
        # for generic action use GenericActionParams
        validated_params_class = GenericActionParams

        return_type = inspect.signature(function).return_annotation
        if return_type is not inspect.Signature.empty:
            validated_output_class = return_type
        elif self.output_class is not None:
            validated_output_class = self.output_class
        else:
            raise TypeError(
                "Action function must specify a return type via type hint or output_class parameter"
            )

        if not issubclass(validated_output_class, ActionOutput) and not isinstance(
            validated_output_class, GenericActionOutput
        ):
            raise TypeError(
                "Return type for action function must be either GenericActionOutput or derived from ActionOutput or GenericActionOutput class."
            )

        logger = getLogger()

        @action_protocol
        @wraps(function)
        def inner(
            params: GenericActionParams,
            soar: SOARClient = self.app.soar_client,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> bool:
            try:
                action_params = validated_params_class.parse_obj(params)
            except Exception as e:
                logger.info(f"Parameter validation error: {e!s}")
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=f"Invalid parameters: {e!s}"),
                    self.app.actions_manager,
                )
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

        inner.params_class = validated_params_class
        inner.meta = ActionMeta(
            action=action_name,
            identifier=action_identifier,
            description=inspect.getdoc(function) or action_name,
            verbose="Generic action for the app.",
            type="generic",
            parameters=validated_params_class,
            output=validated_output_class,
            read_only=False,
            versions="EQ(*)",
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app._dev_skip_in_pytest(function, inner)
        return inner
