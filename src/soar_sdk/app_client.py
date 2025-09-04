from dataclasses import dataclass
from typing import Any, TYPE_CHECKING, Union, Optional
from collections.abc import Mapping

import httpx

from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault

from soar_sdk.abstract import SOARClient, SOARClientAuth, SummaryType

if TYPE_CHECKING:
    pass


@dataclass
class BasicAuth:
    """Basic authentication credentials for the SOAR API."""

    username: str
    password: str


class AppClient(SOARClient[SummaryType]):
    """An adapter between apps built with the SDK, and the APIs exposed by the BaseConnector class.

    Enables apps to access SOAR platform features, without having to import the closed-source "phantom" library directly. In the future, it should be replaced by another class that uses the API to interact with SOAR, instead of BaseConnector.
    """

    def __init__(self) -> None:
        # Call the BaseConnectors init first
        super().__init__()

        self._client = httpx.Client(
            base_url=self.get_soar_base_url(),
            verify=False,  # noqa: S501
        )
        self.csrf_token: str = ""

        self._artifacts_api = Artifact(soar_client=self)
        self._containers_api = Container(soar_client=self)
        self._vault_api = Vault(soar_client=self)
        self.basic_auth: Optional[BasicAuth] = None

        self._summary: Optional[SummaryType] = None
        self._message: Optional[str] = None

    @property
    def client(self) -> httpx.Client:
        """The HTTP client used for making requests to the SOAR API."""
        return self._client

    @property
    def artifact(self) -> Artifact:
        """The SOAR Artifacts API."""
        return self._artifacts_api

    @property
    def container(self) -> Container:
        """The SOAR Containers API."""
        return self._containers_api

    @property
    def vault(self) -> Vault:
        """The SOAR Vault API."""
        return self._vault_api

    def update_client(self, soar_auth: SOARClientAuth, asset_id: str) -> None:
        """Update the SOAR client with the given authentication and asset ID."""
        self.authenticate_soar_client(soar_auth)
        self._containers_api.set_executing_asset(asset_id)

    def authenticate_soar_client(self, soar_auth: SOARClientAuth) -> None:
        """Authenticate the SOAR client with the given authentication credentials."""
        session_id = soar_auth.user_session_token
        self._client = httpx.Client(
            base_url=soar_auth.base_url,
            verify=False,  # noqa: S501
        )
        if session_id:
            self.__login()
        else:
            if soar_auth.username:
                self.__login()
                self.__basic_auth = BasicAuth(soar_auth.username, soar_auth.password)
                session_id = self.get_session_id()

        if session_id:
            current_cookies = self._client.headers.get("Cookie", "")
            update_cookies = f"sessionid={session_id};{current_cookies}"
            self._client.headers.update({"Cookie": update_cookies})

    def __login(self) -> None:
        response = self._client.get("/login")
        response.raise_for_status()
        self.csrf_token = response.cookies.get("csrftoken") or ""
        self._client.cookies.update(response.cookies)
        self._client.headers.update({"X-CSRFToken": self.csrf_token})
        cookies = f"csrftoken={self.csrf_token}"
        self._client.headers.update({"Cookie": cookies})

    def get_session_id(self) -> str:
        """Get the session ID for the authenticated user."""
        self._client.post(
            "/login",
            data={
                "username": self.__basic_auth.username,
                "password": self.__basic_auth.password,
                "csrfmiddlewaretoken": self.csrf_token,
            },
            headers={"Referer": f"{self._client.base_url}/login"},
        )
        session_id = self._client.cookies.get("sessionid")
        return session_id or ""

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
        headers.update({"Referer": f"{self._client.base_url}/{endpoint}"})
        response = self._client.delete(
            endpoint,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth
            or httpx.BasicAuth(self.__basic_auth.username, self.__basic_auth.password)
            if self.basic_auth
            else None,  # type: ignore[arg-type]
            timeout=timeout,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

    def set_summary(self, summary: SummaryType) -> None:
        """Set the summary for the action result."""
        self._summary = summary

    def set_message(self, message: str) -> None:
        """Set the message for the action result."""
        self._message = message

    def get_summary(self) -> Optional[SummaryType]:
        """Get the summary for the action result."""
        return self._summary

    def get_message(self) -> Optional[str]:
        """Get the message for the action result."""
        return self._message
