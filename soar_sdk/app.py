import inspect
import sys
from typing import Any, Optional, Type, Union

from soar_sdk.action_results import ActionResult
from soar_sdk.app_runner import AppRunner
from soar_sdk.connector import AppConnector
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params
from soar_sdk.types import MetaDescribed, meta_described


class App:
    def __init__(self, connector_class=AppConnector):
        self.connector = connector_class(self)

        self._actions: dict[str, MetaDescribed] = {}

    def add_result(self, action_result: ActionResult):
        self.connector.add_action_result(action_result)

    def get_results(self):
        return self.connector.get_action_results()

    def get_soar_base_url(self):
        return self.connector.get_soar_base_url()

    def get_action(self, identifier: str):
        return self.get_actions()[identifier]

    def get_actions(self):
        return self._actions

    def run(self):
        runner = AppRunner(self)
        runner.run()

    def handle(self, input_data: str, handle: Optional[Any] = None):
        """
        Runs handling of the input data on connector
        """
        self.connector.print_progress_message = True
        return self.connector.handle(input_data, handle)

    __call__ = handle  # the app instance can be called for ease of use by spawn3

    def set_action(
        self, action_identifier: str, wrapped_function: MetaDescribed
    ) -> None:
        """
        Sets the handler for the function that can be called by the BaseConnector.
        The wrapped function called by the BaseConnector will be called using the old
        backward-compatible declaration.

        :param action_identifier: name of the action
        :param wrapped_function: the wrapped function that should
                                 be called by the BaseConnector
        :return: None
        """
        self._actions[action_identifier] = wrapped_function

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
        # TODO: Consider some refactoring and extracting parts of the code
        #       for better readability.

        def app_action(function):
            """
            Decorates the action handling function adding the passed specific
            meta information on the action.
            """
            action_identifier = identifier or function.__name__

            @meta_described
            def inner(
                params: Optional[Union[Params, dict[str, Any]]] = None,
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

                if not params:  # TODO: add tests coverage here (None, {} etc.)
                    result = function(self, *args, **kwargs)
                else:
                    if isinstance(params, Params):
                        parsed_params = params
                    else:
                        # Params model class is defined in the meta
                        # try parsing the object using pydantic functionality
                        params_expected_klass: Type[Params] = inner.params_klass
                        parsed_params = params_expected_klass.parse_obj(params)
                    result = function(self, parsed_params, *args, **kwargs)

                # Handling multiple ways of returning response from action
                # This is to simplify ActionResult use, but also keep
                # partial backward compatibility for ease of existing
                # apps migration.
                if isinstance(result, ActionResult):
                    self.connector.add_action_result(result)
                    return result.get_status()
                if isinstance(result, tuple) and 2 <= len(result) <= 3:
                    action_result = ActionResult(*result)
                    self.connector.add_action_result(action_result)
                    return result[0]
                return result

            action_name = name or str(action_identifier.replace("_", " "))

            the_params_klass = params_klass or Params
            if params_klass is None:
                # try to fetch from the function args typehints
                spec = inspect.getfullargspec(function)
                if not len(spec.args):
                    raise TypeError(
                        "Action function must accept at least the ctx: App "
                        "positional argument"
                    )
                if len(spec.args) >= 2:
                    params_arg = spec.args[1]
                    annotated_params_type: Optional[type] = spec.annotations.get(
                        params_arg
                    )
                    if annotated_params_type is None:
                        raise TypeError(
                            f"Proper params type for action {action_name} is not set. "
                            "It should be derived from Params class"
                        )
                    if issubclass(annotated_params_type, Params):
                        the_params_klass = annotated_params_type
                    else:
                        raise TypeError(
                            f"Proper params type for action {action_name} is not "
                            f"derived from Params class."
                        )

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

            self.set_action(action_identifier, inner)

            if "pytest" in sys.modules and function.__name__.startswith("test_"):
                # when creating action function starting with "test_"
                # it will confuse pytest into using it as a test
                # when importing it in the test files
                # marking it for skip, solves the issue
                # TODO: try adding some test on this
                import pytest

                pytest.mark.skip(inner)

            return inner

        return app_action

    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ):
        self.connector.debug_print(tag, dump_object)
