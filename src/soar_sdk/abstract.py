from abc import ABC, abstractmethod
from typing import Any, Optional, Union
from collections.abc import Mapping, Iterable, AsyncIterable

from soar_sdk.input_spec import InputSpecification
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.action_results import ActionResult
from soar_sdk.apis.vault import Vault
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
import httpx

JSONType = Union[dict[str, Any], list[Any], str, int, float, bool, None]


class SOARClient(ABC):
    """
    A unified API interface for performing actions on SOAR Platform.
    Replaces previously used BaseConnector API interface.

    This interface is still a subject to change, so consider it to be WIP.
    """

    ingestion_state: dict
    auth_state: dict
    asset_cache: dict

    @property
    @abstractmethod
    def client(self) -> httpx.Client:
        """
        Subclasses must define the client property.
        """
        pass

    @property
    @abstractmethod
    def vault(self) -> Vault:
        """
        Subclasses must define the vault property.
        """
        pass

    @property
    @abstractmethod
    def artifact(self) -> Artifact:
        """
        Api interface to manage SOAR artifacts.
        """
        pass

    @property
    @abstractmethod
    def container(self) -> Container:
        """
        Api interface to manage SOAR containers.
        """

    @abstractmethod
    def get(
        self,
        endpoint: str,
        *,
        params: Optional[Union[dict[str, Any], httpx.QueryParams]] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        timeout: Optional[httpx.Timeout] = None,
        auth: Optional[Union[httpx.Auth, tuple[str, str]]] = None,
        follow_redirects: bool = False,
        extensions: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform a GET request to the specfic endpoint using the soar client
        """
        pass

    @abstractmethod
    def post(
        self,
        endpoint: str,
        *,
        content: Optional[
            Union[str, bytes, Iterable[bytes], AsyncIterable[bytes]]
        ] = None,
        data: Optional[Mapping[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        json: Optional[JSONType] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        auth: Optional[Union[httpx.Auth, tuple[str, str]]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        follow_redirects: bool = True,
        extensions: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform a POST request to the specfic endpoint using the soar client
        """
        pass

    @abstractmethod
    def put(
        self,
        endpoint: str,
        *,
        content: Optional[
            Union[str, bytes, Iterable[bytes], AsyncIterable[bytes]]
        ] = None,
        data: Optional[Mapping[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        json: Optional[JSONType] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        auth: Optional[Union[httpx.Auth, tuple[str, str]]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        follow_redirects: bool = True,
        extensions: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform a PUT request to the specfic endpoint using the soar client
        """
        pass

    @abstractmethod
    def delete(
        self,
        endpoint: str,
        *,
        params: Optional[Union[dict[str, Any], httpx.QueryParams]] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        auth: Optional[Union[httpx.Auth, tuple[str, str]]] = None,
        timeout: Optional[httpx.Timeout] = None,
        follow_redirects: bool = False,
        extensions: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform a DELETE request to the specfic endpoint using the soar client
        """
        pass

    @abstractmethod
    def get_soar_base_url(self) -> str:
        pass

    @abstractmethod
    def update_client(self, input_data: InputSpecification) -> None:
        """
        Updates the client before an actions run with the input data. An example of what this function might do is authenticate the api client.
        """
        pass

    @abstractmethod
    def get_product_installation_id(self) -> str:
        pass

    @abstractmethod
    def set_csrf_info(self, token: str, referer: str) -> None:
        pass

    @abstractmethod
    def handle_action(self, param: dict[str, Any]) -> None:
        """
        The actual handling method that is being called internally by BaseConnector
        at the momment.
        :param param: dict containing parameters for the action
        """
        pass

    @abstractmethod
    def handle(
        self,
        input_data: InputSpecification,
        handle: Optional[int] = None,
    ) -> str:
        """Public method for handling the input data with the selected handler"""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def finalize(self) -> bool:
        pass

    @abstractmethod
    def add_result(self, action_result: ActionResult) -> PhantomActionResult:
        pass

    @abstractmethod
    def get_results(self) -> list[ActionResult]:
        pass

    @abstractmethod
    def error(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        pass

    @abstractmethod
    def save_progress(
        self,
        progress_str_const: str,
        *unnamed_format_args: object,
        **named_format_args: object,
    ) -> None:
        pass

    @abstractmethod
    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        pass

    @abstractmethod
    def add_exception(self, exception: Exception) -> None:
        pass
