import inspect
import json
import sys
from functools import wraps
from typing import Any, Optional, Union, Callable
from collections.abc import Iterator

from soar_sdk.asset import BaseAsset
from soar_sdk.input_spec import InputSpecification
from soar_sdk.compat import (
    MIN_PHANTOM_VERSION,
    PythonVersion,
)
from soar_sdk.shims.phantom_common.app_interface.app_interface import SoarRestClient
from soar_sdk.abstract import SOARClient, SOARClientAuth
from soar_sdk.action_results import ActionResult
from soar_sdk.actions_manager import ActionsManager
from soar_sdk.app_cli_runner import AppCliRunner
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.meta.webhooks import WebhookMeta
from soar_sdk.params import Params
from soar_sdk.params import OnPollParams
from soar_sdk.app_client import AppClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.types import Action, action_protocol
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure
from soar_sdk.webhooks.routing import Router
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse, WebhookHandler

import uuid
from soar_sdk.app_decorators import (
    TestConnectivityDecorator,
    ActionDecorator,
    ViewHandlerDecorator,
)


def is_valid_uuid(value: str) -> bool:
    """Validates if a string is a valid UUID"""
    try:
        return str(uuid.UUID(value)).lower() == value.lower()
    except ValueError:
        return False


class App:
    def __init__(
        self,
        *,
        name: str,
        app_type: str,
        logo: str,
        logo_dark: str,
        product_vendor: str,
        product_name: str,
        publisher: str,
        appid: str,
        python_version: Optional[list[PythonVersion]] = None,
        min_phantom_version: str = MIN_PHANTOM_VERSION,
        fips_compliant: bool = False,
        asset_cls: type[BaseAsset] = BaseAsset,
    ) -> None:
        self.asset_cls = asset_cls
        self._raw_asset_config: dict[str, Any] = {}
        self.__logger = getLogger()
        if not is_valid_uuid(appid):
            raise ValueError(f"Appid is not a valid uuid: {appid}")

        if python_version is None:
            python_version = PythonVersion.all()

        self.app_meta_info = {
            "name": name,
            "type": app_type,
            "logo": logo,
            "logo_dark": logo_dark,
            "product_vendor": product_vendor,
            "product_name": product_name,
            "publisher": publisher,
            "python_version": python_version,
            "min_phantom_version": min_phantom_version,
            "fips_compliant": fips_compliant,
            "appid": appid,
        }

        self.actions_manager: ActionsManager = ActionsManager()
        self.soar_client: SOARClient = AppClient()

    def get_actions(self) -> dict[str, Action]:
        """
        Returns the list of actions registered in the app.
        """
        return self.actions_manager.get_actions()

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
        self.__logger.handler.set_handle(handle)
        soar_auth = App.create_soar_client_auth_object(input_data)
        self.soar_client.update_client(soar_auth, input_data.asset_id)
        return self.actions_manager.handle(input_data, handle=handle)

    @staticmethod
    def create_soar_client_auth_object(
        input_data: InputSpecification,
    ) -> SOARClientAuth:
        """
        Creates a SOARClientAuth object based on the input data.
        This is used to authenticate the SOAR client before running actions.
        """
        if input_data.user_session_token:
            return SOARClientAuth(
                user_session_token=input_data.user_session_token,
                base_url=ActionsManager.get_soar_base_url(),
            )
        elif input_data.soar_auth:
            return SOARClientAuth(
                username=input_data.soar_auth.username,
                password=input_data.soar_auth.password,
                base_url=input_data.soar_auth.phantom_url,
            )
        else:
            return SOARClientAuth(base_url=ActionsManager.get_soar_base_url())

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
        view_handler: Optional[Callable] = None,
        versions: str = "EQ(*)",
    ) -> ActionDecorator:
        """
        Returns a decorator instance for the action handling function attaching action
        specific meta information to the function.
        """
        return ActionDecorator(
            app=self,
            name=name,
            identifier=identifier,
            description=description,
            verbose=verbose,
            action_type=action_type,
            read_only=read_only,
            params_class=params_class,
            output_class=output_class,
            view_handler=view_handler,
            versions=versions,
        )

    def test_connectivity(self) -> TestConnectivityDecorator:
        """
        Returns a decorator instance for test connectivity attaching action
        specific meta information to the function.
        """
        return TestConnectivityDecorator(self)

    def on_poll(self) -> Callable[[Callable], Action]:
        """
        Decorator for the on_poll action.

        The decorated function must be a generator (using yield) or return an Iterator that yields Container and/or Artifact objects. Only one on_poll action is allowed per app.

        Usage:
        If a Container is yielded first, all subsequent Artifacts will be added to that container unless they already have a `container_id`.
        If an `Artifact` is yielded without a container and no `container_id` is set, it will be skipped.
        """

        def on_poll_decorator(function: Callable) -> Action:
            if self.actions_manager.get_action("on_poll"):
                raise TypeError(
                    "The 'on_poll' decorator can only be used once per App instance."
                )

            # Check if function is generator function or has a return type annotation of iterator
            is_generator = inspect.isgeneratorfunction(function)
            signature = inspect.signature(function)
            has_iterator_return = False

            # Check if the return annotation is an Iterator type
            if (
                signature.return_annotation != inspect.Signature.empty
                and hasattr(signature.return_annotation, "__origin__")
                and signature.return_annotation.__origin__ is Iterator
            ):
                has_iterator_return = True

            if not (is_generator or has_iterator_return):
                raise TypeError(
                    "The on_poll function must be a generator (use 'yield') or return an Iterator."
                )

            action_identifier = "on_poll"
            action_name = "on poll"

            # Use OnPollParams for on_poll actions
            validated_params_class = OnPollParams
            logger = self.__logger

            @action_protocol
            @wraps(function)
            def inner(
                params: OnPollParams,
                client: SOARClient = self.soar_client,
                *args: Any,  # noqa: ANN401
                **kwargs: Any,  # noqa: ANN401
            ) -> bool:
                try:
                    # Validate poll params
                    try:
                        action_params = validated_params_class.parse_obj(params)
                    except Exception as e:
                        logger.info(f"Parameter validation error: {e!s}")
                        return self._adapt_action_result(
                            ActionResult(
                                status=False, message=f"Invalid parameters: {e!s}"
                            ),
                            self.actions_manager,
                        )

                    kwargs = self._build_magic_args(function, client=client, **kwargs)

                    result = function(action_params, *args, **kwargs)

                    # Check if container_id is provided in params
                    container_id = getattr(params, "container_id", None)
                    container_created = False

                    for item in result:
                        # Check if the item is a Container
                        if isinstance(item, Container):
                            # TODO: Change save_container for incorporation with container.create()
                            container = item.to_dict()  # Convert for saving
                            ret_val, message, cid = self.actions_manager.save_container(
                                container
                            )
                            logger.info(f"Creating container: {container['name']}")

                            if ret_val:
                                container_id = cid
                                container_created = True
                                item.container_id = container_id

                            # Covered by test_on_poll::test_on_poll_yields_container_duplicate, but branch coverage detection on generator functions is wonky
                            if (
                                "duplicate container found" in message.lower()
                            ):  # pragma: no cover
                                logger.info(
                                    "Duplicate container found, reusing existing container"
                                )

                            continue

                        # Check for Artifact
                        if not isinstance(item, Artifact):
                            logger.info(
                                f"Warning: Item is not a Container or Artifact, skipping: {item}"
                            )
                            continue

                        artifact_dict = item.to_dict()  # Convert for saving

                        if (
                            not container_id
                            and not container_created
                            and "container_id" not in artifact_dict
                        ):
                            # No container for this artifact
                            logger.info(
                                f"Warning: Artifact has no container, skipping: {item}"
                            )
                            continue

                        if container_id and "container_id" not in artifact_dict:
                            # Set the container_id
                            artifact_dict["container_id"] = container_id
                            item.container_id = container_id

                        # TODO: Change save_artifact for incorporation with artifact.create()
                        self.actions_manager.save_artifacts([artifact_dict])
                        logger.info(
                            f"Added artifact: {artifact_dict.get('name', 'Unnamed artifact')}"
                        )

                    return self._adapt_action_result(
                        ActionResult(status=True, message="Polling complete"),
                        self.actions_manager,
                    )
                except ActionFailure as e:
                    e.set_action_name(action_name)
                    return self._adapt_action_result(
                        ActionResult(status=False, message=str(e)),
                        self.actions_manager,
                    )
                except Exception as e:
                    self.actions_manager.add_exception(e)
                    logger.info(f"Error during polling: {e!s}")
                    return self._adapt_action_result(
                        ActionResult(status=False, message=str(e)),
                        self.actions_manager,
                    )

            inner.params_class = validated_params_class

            # Custom ActionMeta class for on_poll (has no output)
            class OnPollActionMeta(ActionMeta):
                def dict(self, *args: object, **kwargs: object) -> dict[str, Any]:
                    data = super().dict(*args, **kwargs)
                    # Poll actions have no output
                    data["output"] = []
                    return data

            inner.meta = OnPollActionMeta(
                action=action_name,
                identifier=action_identifier,
                description=inspect.getdoc(function) or action_name,
                verbose="Callback action for the on_poll ingest functionality",
                type="ingest",
                read_only=True,
                parameters=validated_params_class,
                versions="EQ(*)",
            )

            self.actions_manager.set_action(action_identifier, inner)
            self._dev_skip_in_pytest(function, inner)
            return inner

        return on_poll_decorator

    def view_handler(
        self,
        *,
        template: Optional[str] = None,
    ) -> ViewHandlerDecorator:
        """
        Decorator for custom view functions with output parsing and template rendering.

        The decorated function receives parsed ActionOutput objects and can return either a dict for template rendering, HTML string, or component data model.
        If a template is provided, dict results will be rendered using the template. Component type is automatically inferred from the return type annotation.

        Usage:
            @app.view_handler(template="my_template.html")
            def my_view(outputs: List[MyActionOutput]) -> dict:
                return {"data": outputs[0].some_field}

            @app.view_handler()
            def my_chart_view(outputs: List[MyActionOutput]) -> PieChartData:
                return PieChartData(title="Chart", labels=["A", "B"], values=[1, 2], colors=["red", "blue"])
        """
        return ViewHandlerDecorator(self, template=template)

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
        This is used to pass the soar client and asset to the action function, when requested
        """
        sig = inspect.signature(function)
        magic_args: dict[str, object] = {
            "soar": self.soar_client,
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
        inheritance. This is automatically covered by AppClient, but can be also
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
        actions_manager: ActionsManager,
        action_params: Optional[Params] = None,
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
            param_dict = action_params.dict() if action_params else None
            result = ActionResult(
                status=True,
                message="",
                param=param_dict,
            )
            result.add_data(output_dict)

        if isinstance(result, ActionResult):
            actions_manager.add_result(result)
            return result.get_status()
        if isinstance(result, tuple) and 2 <= len(result) <= 3:
            action_result = ActionResult(*result)
            actions_manager.add_result(action_result)
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

    webhook_meta: Optional[WebhookMeta] = None
    webhook_router: Optional[Router] = None

    def enable_webhooks(
        self,
        default_requires_auth: bool = True,
        default_allowed_headers: Optional[list[str]] = None,
        default_ip_allowlist: Optional[list[str]] = None,
    ) -> "App":
        if default_allowed_headers is None:
            default_allowed_headers = []
        if default_ip_allowlist is None:
            default_ip_allowlist = ["0.0.0.0/0", "::/0"]

        self.webhook_meta = WebhookMeta(
            handler=None,  # The handler is set by the ManifestProcessor when generating the final manifest
            requires_auth=default_requires_auth,
            allowed_headers=default_allowed_headers,
            ip_allowlist=default_ip_allowlist,
        )

        self.webhook_router = Router()

        return self

    def webhook(
        self, url_pattern: str, allowed_methods: Optional[list[str]] = None
    ) -> Callable[[WebhookHandler], WebhookHandler]:
        """
        Decorator for registering a webhook handler.
        """

        def decorator(function: WebhookHandler) -> WebhookHandler:
            """
            Decorator for the webhook handler function. Adds the specific meta
            information to the action passed to the generator. Validates types used on
            the action arguments and adapts output for fast and seamless development.
            """
            if self.webhook_router is None:
                raise RuntimeError("Webhooks are not enabled for this app.")

            @wraps(function)
            def webhook_wrapper(
                request: WebhookRequest,
            ) -> WebhookResponse:
                # Inject soar_client if the function expects it
                kwargs = {}
                sig = inspect.signature(function)
                if "soar" in sig.parameters:
                    kwargs["soar"] = self.soar_client
                return function(request, **kwargs)

            self.webhook_router.add_route(
                url_pattern,
                webhook_wrapper,
                methods=allowed_methods,
            )

            return webhook_wrapper

        return decorator

    def handle_webhook(
        self,
        method: str,
        headers: dict[str, str],
        path_parts: list[str],
        query: dict[str, Union[str, list[str], None]],
        body: Optional[str],
        asset: dict,
        soar_rest_client: SoarRestClient,
    ) -> dict:
        """
        Handles the incoming webhook request.
        """
        if self.webhook_router is None:
            raise RuntimeError("Webhooks are not enabled for this app.")

        self._raw_asset_config = asset

        _, soar_auth_token = soar_rest_client.session.headers["Cookie"].split("=")
        asset_id = soar_rest_client.asset_id
        soar_base_url = soar_rest_client.base_url
        soar_auth = SOARClientAuth(
            user_session_token=soar_auth_token,
            base_url=soar_base_url,
        )
        self.soar_client.update_client(soar_auth, asset_id)

        normalized_query = {}
        for key, value in query.items():
            # Normalize query parameters to always be a list
            # This is needed because SOAR prior to 7.0.0 used to flatten query parameters to the last item per key
            # SOAR 7.0.0+ will normalize all query parameters to lists, with an "empty" parameter expressed as a list containing an empty string
            if value is None:
                normalized_query[key] = [""]
            elif isinstance(value, list):
                normalized_query[key] = value
            else:
                normalized_query[key] = [value]

        request = WebhookRequest(
            method=method,
            headers=headers,
            path_parts=path_parts,
            query=normalized_query,
            body=body,
            asset=self.asset,
            soar_auth_token=soar_auth_token,
            soar_base_url=soar_base_url,
            asset_id=asset_id,
        )

        response = self.webhook_router.handle_request(request)
        if not isinstance(response, WebhookResponse):
            raise TypeError(
                f"Webhook handler must return a WebhookResponse, got {type(response)}"
            )
        return response.dict()
