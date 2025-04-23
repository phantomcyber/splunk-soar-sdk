import inspect
import json
import sys
from functools import wraps
from typing import Any, Optional, Union, Callable


from soar_sdk.asset import BaseAsset
from soar_sdk.input_spec import InputSpecification
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.actions_provider import ActionsProvider
from soar_sdk.app_cli_runner import AppCliRunner
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from soar_sdk.types import Action, action_protocol


class App:
    def __init__(
        self,
        *,
        asset_cls: type[BaseAsset] = BaseAsset,
        legacy_connector_class: Optional[type[BaseConnector]] = None,
    ) -> None:
        self.asset_cls = asset_cls
        self._raw_asset_config: dict[str, Any] = {}

        self.actions_provider = ActionsProvider(legacy_connector_class)

    def get_actions(self) -> dict[str, Action]:
        """
        Returns the list of actions registered in the app.
        """
        return self.actions_provider.get_actions()

    def cli(self) -> None:
        """
        This is just a handy shortcut for reducing imports in the main app code.
        It uses AppRunner to run locally app the same way as main() in the legacy
        connectors.
        """
        runner = AppCliRunner(self)
        runner.run()

    def handle(self, raw_input_data: str, handle: Optional[int] = None) -> str:
        """
        Runs handling of the input data on connector.
        NOTE: handle is actually a pointer address to spawn's internal state.
        In versions of SOAR >6.4.1, handle will not be passed to the app.
        """
        input_data = InputSpecification.parse_obj(json.loads(raw_input_data))
        self._raw_asset_config = input_data.config.get_asset_config()
        return self.actions_provider.handle(input_data, handle=handle)

    __call__ = handle  # the app instance can be called for ease of use by spawn3

    @property
    def asset(self) -> BaseAsset:
        """
        Returns the asset instance for the app.
        """
        if not hasattr(self, "_asset"):
            self._asset = self.asset_cls.parse_obj(self._raw_asset_config)
        return self._asset

    def action(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        description: Optional[str] = None,
        verbose: str = "",
        action_type: str = "generic",  # TODO: consider introducing enum type for that
        read_only: bool = True,
        params_class: Optional[type[Params]] = None,
        output_class: Optional[type[ActionOutput]] = None,
        versions: str = "EQ(*)",
    ) -> Callable[[Callable], Action]:
        """
        Generates a decorator for the action handling function attaching action
        specific meta information to the function.
        """

        def app_action(function: Callable) -> Action:
            """
            Decorator for the action handling function. Adds the specific meta
            information to the action passed to the generator. Validates types used on
            the action arguments and adapts output for fast and seamless development.
            """
            action_identifier = identifier or function.__name__
            if action_identifier == "test_connectivity":
                raise TypeError(
                    "The 'test_connectivity' action identifier is reserved and cannot be used. Please use the test_connectivity decorator instead."
                )
            if self.actions_provider.get_action(action_identifier):
                raise TypeError(
                    f"Action identifier '{action_identifier}' is already used. Please use a different identifier."
                )

            action_name = name or str(action_identifier.replace("_", " "))

            spec = inspect.getfullargspec(function)
            validated_params_class = self._validate_params_class(
                action_name, spec, params_class
            )

            return_type = inspect.signature(function).return_annotation
            if return_type is not inspect.Signature.empty:
                validated_output_class = return_type
            elif output_class is not None:
                validated_output_class = output_class
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
                client: SOARClient = self.actions_provider.soar_client,
                *args: Any,  # noqa: ANN401
                **kwargs: Any,  # noqa: ANN401
            ) -> bool:
                """
                Validates input params and adapts the results from the action.
                """
                action_params = self._validate_params(params, action_name)
                kwargs = self._build_magic_args(function, client=client, **kwargs)

                result = function(action_params, *args, **kwargs)
                return self._adapt_action_result(result, client)

            # setting up meta information for the decorated function
            inner.params_class = validated_params_class
            inner.meta = ActionMeta(
                action=action_name,
                identifier=identifier or function.__name__,
                description=description or inspect.getdoc(function) or action_name,
                verbose=verbose,  # FIXME: must start with a capital and end with full stop
                type=action_type,
                read_only=read_only,
                parameters=validated_params_class,
                output=validated_output_class,  # FIXME: all output need to contain params
                versions=versions,
            )

            self.actions_provider.set_action(action_identifier, inner)

            self._dev_skip_in_pytest(function, inner)

            return inner

        return app_action

    def test_connectivity(self) -> Callable[[Callable], Action]:
        """
        Generates a decorator for test connectivity attaching action
        specific meta information to the function.
        """

        def test_con_function(function: Callable) -> Action:
            """
            Decorator for the test connectivity function. Makes sure that only 1 function
            in the app is decorated with this decorator and attaches generic metadata to the
            action. Validates that the only param passed is the SOARClient and adapts the return
            value based on the success or failure of test connectivity.
            """

            if self.actions_provider.get_action("test_connectivity"):
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
                client: SOARClient = self.actions_provider.soar_client,
            ) -> bool:
                kwargs = self._build_magic_args(function, client=client)

                try:
                    result = function(**kwargs)
                    if result is not None:
                        raise RuntimeError(
                            "Test connectivity function must not return any value (return type should be None)."
                        )
                except Exception as e:
                    return self._adapt_action_result(
                        ActionResult(status=False, message=str(e)), client
                    )
                return self._adapt_action_result(
                    ActionResult(status=True, message="Test connectivity successful"),
                    client,
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

            self.actions_provider.set_action(action_identifier, inner)
            self._dev_skip_in_pytest(function, inner)
            return inner

        return test_con_function

    @staticmethod
    def _validate_params_class(
        action_name: str,
        spec: inspect.FullArgSpec,
        params_class: Optional[type[Params]] = None,
    ) -> type[Params]:
        """
        Validates the class used for params argument of the action. Ensures the class
        is defined and provided as it is also used for building the manifest JSON file.
        """
        # validating params argument
        validated_params_class = params_class or Params
        if params_class is None:
            # try to fetch from the function args typehints
            if not len(spec.args):
                raise TypeError(
                    "Action function must accept at least the params positional argument"
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
                validated_params_class = annotated_params_type
            else:
                raise TypeError(
                    f"Proper params type for action {action_name} is not derived from Params class."
                )
        return validated_params_class

    def _build_magic_args(self, function: Callable, **kwargs: object) -> dict[str, Any]:
        """
        Builds the auto-magic optional arguments for an action function.
        This is used to pass the client and asset to the action function, when requested
        """
        sig = inspect.signature(function)
        magic_args: dict[str, object] = {
            "client": self.actions_provider.soar_client,
            "asset": self.asset,
        }

        for name, value in magic_args.items():
            given_value = kwargs.pop(name, None)
            if name in sig.parameters:
                # Give the original kwargs precedence over the magic args
                kwargs[name] = given_value or value

        return kwargs

    @staticmethod
    def _validate_params(params: Params, action_name: str) -> Params:
        """
        Validates input params, checking them against the use of proper Params class
        inheritance. This is automatically covered by AppConnector, but can be also
        useful for when using in testing with mocked SOARClient implementation.
        """
        if not isinstance(params, Params):
            raise TypeError(
                f"Provided params are not inheriting from Params class for action {action_name}"
            )
        return params

    @staticmethod
    def _adapt_action_result(
        result: Union[ActionOutput, ActionResult, tuple[bool, str], bool],
        client: SOARClient,
    ) -> bool:
        """
        Handles multiple ways of returning response from action. The simplest result
        can be returned from the action as a tuple of success boolean value and an extra
        message to add.

        For backward compatibility, it also supports returning ActionResult object as
        in the legacy Connectors.
        """
        if isinstance(result, ActionOutput):
            output_dict = result.dict()
            result = ActionResult(
                status=True,
                message="",
                param=output_dict,
            )

        if isinstance(result, ActionResult):
            client.add_result(result)
            return result.get_status()
        if isinstance(result, tuple) and 2 <= len(result) <= 3:
            action_result = ActionResult(*result)
            client.add_result(action_result)
            return result[0]
        return False

    @staticmethod
    def _dev_skip_in_pytest(function: Callable, inner: Action) -> None:
        """
        When running pytest, all actions with a name starting with `test_`
        will be treated as test. This method will mark them as to be skipped.
        """
        if "pytest" in sys.modules and function.__name__.startswith("test_"):
            # importing locally to not require this package in the runtime requirements
            import pytest

            pytest.mark.skip(inner)
