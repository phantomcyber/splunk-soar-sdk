from abc import abstractmethod
from typing import Any, Optional, Union, Generic, TypeVar
from collections.abc import Mapping, Iterable, AsyncIterable

from soar_sdk.apis.vault import Vault
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.action_results import ActionOutput
import httpx
from pydantic.dataclasses import dataclass
from pydantic import validator

JSONType = Union[dict[str, Any], list[Any], str, int, float, bool, None]
SummaryType = TypeVar("SummaryType", bound=ActionOutput)


@dataclass
class SOARClientAuth:
    """Authentication credentials for the SOAR API."""

    base_url: str
    username: str = ""
    password: str = ""
    user_session_token: str = ""

    @validator("base_url")
    def validate_phantom_url(cls, value: str) -> str:
        """Validate and format the base URL for the SOAR API."""
        return (
            f"https://{value}"
            if not value.startswith(("http://", "https://"))
            else value
        )


class SOARClient(Generic[SummaryType]):
    """A unified API interface for performing actions on SOAR Platform.

    Replaces previously used BaseConnector API interface.
    """

    @property
    @abstractmethod
    def client(self) -> httpx.Client:
        """Generic HTTP client. Subclasses must define."""
        pass

    @property
    @abstractmethod
    def vault(self) -> Vault:
        """Object governing interaction with the SOAR Vault API. Subclasses must define."""
        pass

    @property
    @abstractmethod
    def artifact(self) -> Artifact:
        """Object governing interaction with the SOAR artifact API. Subclasses must define."""
        pass

    @property
    @abstractmethod
    def container(self) -> Container:
        """Object governing interaction with the SOAR container API. Subclasses must define."""
        pass

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
        """Perform a GET request to the specific endpoint using the SOAR client."""
        response = self.client.get(
            endpoint,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            auth=auth,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

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
        """Perform a POST request to the specific endpoint using the SOAR client."""
        headers = headers or {}
        headers.update({"Referer": f"{self.client.base_url}/{endpoint}"})
        response = self.client.post(
            endpoint,
            headers=headers,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            timeout=timeout,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

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
        """Perform a PUT request to the specific endpoint using the SOAR client."""
        headers = headers or {}
        headers.update({"Referer": f"{self.client.base_url}/{endpoint}"})
        response = self.client.put(
            endpoint,
            headers=headers,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            timeout=timeout,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

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
        """Perform a DELETE request to the specific endpoint using the SOAR client."""
        headers = headers or {}
        headers.update({"Referer": f"{self.client.base_url}/{endpoint}"})
        response = self.client.delete(
            endpoint,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,  # type: ignore[arg-type]
            timeout=timeout,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

    def get_soar_base_url(self) -> str:
        """Get the base URL for the running SOAR system. Example: https://splunk.soar/"""
        return "https://localhost:9999/"

    @abstractmethod
    def update_client(self, soar_auth: SOARClientAuth, asset_id: str) -> None:
        """Hook to update the SOAR API client before any actions run with the input data.

        An example of what this function might do is authenticate the API client.
        """
        pass

    @abstractmethod
    def set_summary(self, summary: SummaryType) -> None:
        """Set the custom summary object for the action run."""
        pass

    @abstractmethod
    def set_message(self, message: str) -> None:
        """Set the summary message for the action run."""
        pass

    @abstractmethod
    def get_summary(self) -> Optional[SummaryType]:
        """Get the summary for the action run."""
        pass

    @abstractmethod
    def get_message(self) -> Optional[str]:
        """Get the summary message for the action run."""
        pass
