import inspect
from functools import wraps
from typing import Callable, Optional

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action, action_protocol
from soar_sdk.exceptions import ActionFailure
from soar_sdk.async_utils import run_async_if_needed
import traceback

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soar_sdk.app import App


class ConnectivityTestDecorator:
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
                result = run_async_if_needed(result)
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
