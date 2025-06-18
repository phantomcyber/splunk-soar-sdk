
from typing import Optional, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass

from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from soar_sdk.logging import getLogger
logger = getLogger()

if TYPE_CHECKING:
    from soar_sdk.app import App


@dataclass
class DeferredAction:
    """Stores information about an action to be registered later."""
    decorator_method: str
    function: Callable
    kwargs: dict[str, Any]


class ActionGroup:
    """
    Represents a group of actions that can be executed together.
    This class works like Flask's Blueprint paradigm - you can define actions
    on the group, then register the entire group with an App instance.
    
    Example:
        auth_group = ActionGroup(name="auth")
        
        @auth_group.action(name="login")
        def login_action(params: LoginParams) -> LoginOutput:
            # implementation
            pass
            
        app.register_action_group(auth_group)
    """

    def __init__(self, name: str, description: Optional[str] = None):
        self.name = name
        self.description = description
        self._deferred_actions: list[DeferredAction] = []
        self._app: Optional["App"] = None

    @property
    def app(self) -> "App":
        """Get the associated app instance."""
        if self._app is None:
            raise RuntimeError(
                f"ActionGroup '{self.name}' is not registered with an App. "
                "Call app.register_action_group(action_group) first."
            )
        return self._app

    @property
    def soar_client(self):
        """Access to the app's SOAR client."""
        return self.app.soar_client

    @property
    def asset(self):
        """Access to the app's asset."""
        return self.app.asset

    def action(
        self,
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
    ):
        """
        Decorator for registering an action with this ActionGroup.
        The action will be registered with the App when the ActionGroup is registered.
        """
        def decorator(function: Callable):
            # Store the action for later registration
            self._deferred_actions.append(DeferredAction(
                decorator_method="action",
                function=function,
                kwargs={
                    "name": name,
                    "identifier": identifier,
                    "description": description,
                    "verbose": verbose,
                    "action_type": action_type,
                    "read_only": read_only,
                    "params_class": params_class,
                    "output_class": output_class,
                    "view_handler": view_handler,
                    "versions": versions,
                }
            ))
            return function
        return decorator


    def view_handler(self, *, template: Optional[str] = None):
        """
        Decorator for registering a view handler with this ActionGroup.
        """
        def decorator(function: Callable):
            self._deferred_actions.append(DeferredAction(
                decorator_method="view_handler",
                function=function,
                kwargs={"template": template}
            ))
            return function
        return decorator

    def webhook(self, url_pattern: str, allowed_methods: Optional[list[str]] = None):
        """
        Decorator for registering a webhook handler with this ActionGroup.
        """
        def decorator(function: Callable):
            self._deferred_actions.append(DeferredAction(
                decorator_method="webhook",
                function=function,
                kwargs={"url_pattern": url_pattern, "allowed_methods": allowed_methods}
            ))
            return function
        return decorator

    def _register_with_app(self, app: "App") -> None:
        """
        Internal method to register all deferred actions with the app.
        Called by App.register_action_group().
        
        This method handles dependencies between decorators, ensuring that
        view handlers are decorated before they're used by actions.
        """
        self._app = app
        
        decorated_functions = {}
        
        # First pass: Register all non-action decorators (view_handler, webhook, etc.)
        for deferred_action in self._deferred_actions:
            if deferred_action.decorator_method != "action":
                decorator_method = getattr(self._app, deferred_action.decorator_method)
                
                if deferred_action.kwargs:
                    decorator = decorator_method(**deferred_action.kwargs)
                else:
                    decorator = decorator_method()
                
                decorated_function = decorator(deferred_action.function)
                decorated_functions[deferred_action.function] = decorated_function
        
        # Second pass: Register action decorators, updating view_handler references
        for deferred_action in self._deferred_actions:
            if deferred_action.decorator_method == "action":
                # Check if this action has a view_handler that needs to be updated
                kwargs = deferred_action.kwargs.copy()
                logger.debug(
                    f"Registering action {deferred_action.function.__name__} with kwargs: {kwargs}"
                )
                if "view_handler" in kwargs and kwargs["view_handler"] is not None:
                    original_view_handler = kwargs["view_handler"]
                    # Replace with decorated version if available
                    if original_view_handler in decorated_functions:
                        decorated_view_handler = decorated_functions[original_view_handler]
                        kwargs["view_handler"] = decorated_view_handler
                        import inspect
                        logger.debug(
                            f"Updated view_handler for action {deferred_action.function.__name__} from {inspect.signature(original_view_handler)} to {inspect.signature(decorated_view_handler)}"
                        )
                  
                
                decorator_method = getattr(self._app, deferred_action.decorator_method)                
                decorator = decorator_method(**kwargs)                
                decorator(deferred_action.function)

    def __repr__(self) -> str:
        return f"ActionGroup(name='{self.name}', actions={len(self._deferred_actions)})"