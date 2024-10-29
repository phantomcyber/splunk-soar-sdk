import inspect
import sys
from typing import Any, Optional, Type, Union

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.actions_manager import ActionsManager
from soar_sdk.app_runner import AppRunner
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params
from soar_sdk.types import meta_described


class App:
    def __init__(self, legacy_connector_class=None):
        self.manager = ActionsManager(legacy_connector_class)

    def run(self):
        """
        This is just a handy shortcut for reducing imports in the main app code.
        It uses AppRunner to run locally app the same way as main() in the legacy
        connectors.
        """
        runner = AppRunner(self)
        runner.run()

    def handle(self, input_data: str, handle: Optional[Any] = None) -> str:
        """
        Runs handling of the input data on connector
        """
        return self.manager.handle(input_data, handle)

    __call__ = handle  # the app instance can be called for ease of use by spawn3

    def action(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        description: Optional[str] = None,
        verbose: str = "",
        action_type: str = "generic",  # TODO: consider introducing enum type for that
        read_only: bool = True,
        params_klass: Optional[Type[Params]] = None,
        output: Optional[list[str]] = None,
        versions: str = "EQ(*)",
    ):
        """
        Generates a decorator for the action handling function and decorates it
        by passing action specific meta information.
        """

        def app_action(function):
            """
            Decorates the action handling function adding the passed specific
            meta information on the action.
            """
            action_identifier = identifier or function.__name__

            action_name = name or str(action_identifier.replace("_", " "))

            spec = inspect.getfullargspec(function)

            # validating params argument
            the_params_klass = params_klass or Params
            if params_klass is None:
                # try to fetch from the function args typehints
                if not len(spec.args):
                    raise TypeError(
                        "Action function must accept at least the params "
                        "positional argument"
                    )
                params_arg = spec.args[0]
                annotated_params_type: Optional[type] = spec.annotations.get(params_arg)
                if annotated_params_type is None:
                    raise TypeError(
                        f"Action {action_name} has no params type set. "
                        "The params argument must provide type which is derived "
                        "from Params class"
                    )
                if issubclass(annotated_params_type, Params):
                    the_params_klass = annotated_params_type
                else:
                    raise TypeError(
                        f"Proper params type for action {action_name} is not "
                        f"derived from Params class."
                    )

            is_client_expected = len(spec.args) > 1 and "client" in spec.args

            @meta_described
            def inner(
                params: Optional[Union[Params, dict[str, Any]]],
                client: SOARClient = self.manager.soar_client,
                *args,
                **kwargs,
            ):  # pragma: no cover
                """
                This wrapper function is being called by BaseConnector
                following the old compatibility of the function declaration.

                This wrapper injects app context into the function,
                so the handler can access app information and connector
                class for backward compatibility.
                """

                if isinstance(params, Params):
                    action_params = params
                else:
                    raise TypeError(
                        f"Provided params are not inheriting from Params class for action {action_name}"
                    )

                if is_client_expected:
                    result = function(action_params, client, *args, **kwargs)
                else:
                    result = function(action_params, *args, **kwargs)

                # Handling multiple ways of returning response from action
                # This is to simplify ActionResult use, but also keep
                # partial backward compatibility for ease of existing
                # apps migration.
                if isinstance(result, ActionResult):
                    client.add_result(result)
                    return result.get_status()
                if isinstance(result, tuple) and 2 <= len(result) <= 3:
                    action_result = ActionResult(*result)
                    client.add_result(action_result)
                    return result[0]
                return result

            # setting up meta information for the decorated function
            inner.meta = ActionMeta(
                action=action_name,
                identifier=identifier or function.__name__,
                description=description or inspect.getdoc(function) or action_name,
                verbose=verbose,  # FIXME: must start with a capital and end with full stop
                type=action_type,
                read_only=read_only,
                parameters=the_params_klass,
                output=output or [],  # FIXME: all output need to contain params
                versions=versions,
            )
            inner.params_klass = the_params_klass

            self.manager.set_action(action_identifier, inner)

            self._dev_skip_in_pytest(function, inner)

            return inner

        return app_action

    @staticmethod
    def _dev_skip_in_pytest(function, inner):
        """
        When running pytest, all actions with a name starting with `test_`
        will be treated as test. This method will mark them as to be skipped.
        """
        if "pytest" in sys.modules and function.__name__.startswith("test_"):
            # importing locally to not require this package in the runtime requirements
            import pytest

            pytest.mark.skip(inner)
