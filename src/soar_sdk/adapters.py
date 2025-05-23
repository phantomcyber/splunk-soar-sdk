from typing import Any, Optional, Union

from soar_sdk.input_spec import InputSpecification
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.action_results import ActionResult
from soar_sdk.apis.container import Container
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.vault import Vault

from .abstract import SOARClient
import httpx


class LegacyConnectorAdapter(SOARClient):
    def __init__(self, legacy_connector_class: type[BaseConnector]) -> None:
        self.connector = legacy_connector_class()

    def get_soar_base_url(self) -> str:
        return self.connector._get_phantom_base_url()

    def get_product_installation_id(self) -> str:
        return self.connector.get_product_installation_id()

    def set_csrf_info(self, token: str, referer: str) -> None:
        self.connector._set_csrf_info(token, referer)

    def handle_action(self, param: dict[str, Any]) -> None:
        self.connector.handle_action(param)

    @property
    def client(self) -> httpx.Client:
        """
        Returns the client object.
        """
        raise NotImplementedError(
            "The soar client is not supported in legacy connectors."
        )

    @property
    def container(self) -> Container:
        raise NotImplementedError(
            "The container interface is not supported in legacy connectors."
        )

    @property
    def artifact(self) -> Artifact:
        raise NotImplementedError(
            "The artifact interface is not supported in legacy connectors."
        )

    @property
    def vault(self) -> Vault:
        raise NotImplementedError(
            "The vault interface is not supported in legacy connectors."
        )

    def get(self, endpoint: str, **kwargs: object) -> httpx.Response:
        raise NotImplementedError(
            "The vault interface is not supported in legacy connectors."
        )

    def post(self, endpoint: str, **kwargs: object) -> httpx.Response:
        raise NotImplementedError(
            "The vault interface is not supported in legacy connectors."
        )

    def put(self, endpoint: str, **kwargs: object) -> httpx.Response:
        raise NotImplementedError(
            "The vault interface is not supported in legacy connectors."
        )

    def delete(self, endpoint: str, **kwargs: object) -> httpx.Response:
        raise NotImplementedError(
            "The vault interface is not supported in legacy connectors."
        )

    def update_client(self, input_data: InputSpecification) -> None:
        """
        Not implemented in the legacy connector.
        """
        pass

    def handle(
        self,
        input_data: InputSpecification,
        handle: Optional[int] = None,
    ) -> str:
        return self.connector._handle_action(input_data.json(), handle or 0)

    def initialize(self) -> bool:
        return self.connector.initialize()

    def finalize(self) -> bool:
        return self.connector.finalize()

    def add_result(self, action_result: ActionResult) -> PhantomActionResult:
        return self.connector.add_action_result(action_result)

    def get_results(self) -> list:
        return self.connector.get_action_results()

    def save_progress(
        self,
        progress_str_const: str,
        *unnamed_format_args: object,
        **named_format_args: object,
    ) -> None:
        return self.connector.save_progress(
            progress_str_const, *unnamed_format_args, **named_format_args
        )

    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        self.connector.debug_print(tag, dump_object)

    def error(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        self.connector.error_print(tag, dump_object)

    def add_exception(self, exception: Exception) -> None:
        self.connector._BaseConnector__conn_result.add_exception(exception)
