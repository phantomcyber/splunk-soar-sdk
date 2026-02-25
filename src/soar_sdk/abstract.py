from abc import abstractmethod
from collections.abc import AsyncIterable, Iterable, Mapping
from typing import Any, Generic, TypeVar

import httpx
from pydantic import field_validator
from pydantic.dataclasses import dataclass

from soar_sdk.action_results import ActionOutput
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault

JSONType = dict[str, Any] | list[Any] | str | int | float | bool | None
SummaryType = TypeVar("SummaryType", bound=ActionOutput)


@dataclass
class SOARClientAuth:
    """Authentication credentials for the SOAR API."""

    base_url: str
    username: str = ""
    password: str = ""
    user_session_token: str = ""
    # Broker authentication (populated when running on AB)
    user_hash_key: str = ""
    broker_ph_auth_token: str = ""

    @field_validator("base_url")
    @classmethod
    def validate_phantom_url(cls, value: str) -> str:
        """Validate and format the base URL for the SOAR API."""
        return (
            f"https://{value}"
            if not value.startswith(("http://", "https://"))
            else value
        )


class SOARClient(Generic[SummaryType]):
    """An API interface for interacting with the Splunk SOAR Platform."""

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

    @abstractmethod
    def get_executing_container_id(self) -> int:
        """Return the current Container ID passed in the Connector Run Action JSON."""
        pass

    @abstractmethod
    def get_asset_id(self) -> str:
        """Return the current Asset ID passed in the Connector Run Action JSON."""
        pass

    MAX_BULK_FINDINGS = 500

    def create_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Create a single finding in ES via the SOAR proxy."""
        response = self.post(
            "/rest/enterprise_security/findings", json=finding, timeout=30.0
        )
        return response.json()

    def create_findings_bulk(
        self,
        findings: list[dict[str, Any]],
        container_ids: list[int | None] | None = None,
    ) -> dict[str, Any]:
        """Create findings in ES via the SOAR bulk endpoint.

        Accepts up to 500 findings per call. When ``container_ids`` is provided,
        the backend links pre-existing containers to the created findings
        instead of creating new ones.

        Returns the bulk response containing ``status``, ``created``,
        ``failed``, ``findings`` (list of IDs), ``container_ids``
        (list of SOAR container IDs), and ``errors``.
        """
        if not findings:
            return {
                "status": "success",
                "created": 0,
                "failed": 0,
                "findings": [],
                "container_ids": [],
                "errors": [],
            }

        if len(findings) > self.MAX_BULK_FINDINGS:
            raise ValueError(
                f"Maximum {self.MAX_BULK_FINDINGS} findings per request, got {len(findings)}"
            )

        endpoint = "/rest/enterprise_security/findings/bulk_create"
        timeout = max(30.0, len(findings) * 5.0)

        payload: dict[str, Any] | list = findings
        if container_ids:
            payload = {"findings": findings, "container_ids": container_ids}

        response = self.post(endpoint, json=payload, timeout=timeout)
        return response.json()

    def upload_finding_attachment(
        self,
        finding_id: str,
        file_name: str,
        data: bytes,
        source_type: str = "Incident",
        is_raw_email: bool = True,
    ) -> dict[str, Any]:
        """Upload an attachment to a finding via the SOAR proxy."""
        import base64

        endpoint = f"/rest/enterprise_security/findings/{finding_id}/files"
        encoded_data = base64.b64encode(data).decode("utf-8")
        response = self.post(
            endpoint,
            json={
                "file_name": file_name,
                "data": encoded_data,
                "source_type": source_type,
                "is_raw_email": is_raw_email,
            },
            timeout=30.0,
        )
        return response.json()

    def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | httpx.QueryParams | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        follow_redirects: bool = False,
        extensions: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        """Perform a GET request to the specific endpoint using the SOAR client."""
        response = self.client.get(
            endpoint,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            auth=auth or httpx.USE_CLIENT_DEFAULT,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

    def post(
        self,
        endpoint: str,
        *,
        content: str | bytes | Iterable[bytes] | AsyncIterable[bytes] | None = None,
        data: Mapping[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        json: JSONType | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        follow_redirects: bool = True,
        extensions: Mapping[str, Any] | None = None,
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
            auth=auth or httpx.USE_CLIENT_DEFAULT,
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
        content: str | bytes | Iterable[bytes] | AsyncIterable[bytes] | None = None,
        data: Mapping[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        json: JSONType | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        follow_redirects: bool = True,
        extensions: Mapping[str, Any] | None = None,
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
            auth=auth or httpx.USE_CLIENT_DEFAULT,
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
        params: dict[str, Any] | httpx.QueryParams | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        follow_redirects: bool = False,
        extensions: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        """Perform a DELETE request to the specific endpoint using the SOAR client."""
        headers = headers or {}
        headers.update({"Referer": f"{self.client.base_url}/{endpoint}"})
        response = self.client.delete(
            endpoint,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth or httpx.USE_CLIENT_DEFAULT,
            timeout=timeout,
            follow_redirects=follow_redirects,
            extensions=extensions,
        )
        response.raise_for_status()
        return response

    def get_soar_base_url(self) -> str:
        """Get the base URL for the running SOAR system.

        Example:
            https://splunk.soar/
        """
        return "https://localhost:9999/"

    @abstractmethod
    def update_client(
        self, soar_auth: SOARClientAuth, asset_id: str, container_id: int = 0
    ) -> None:
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
    def get_summary(self) -> SummaryType | None:
        """Get the summary for the action run."""
        pass

    @abstractmethod
    def get_message(self) -> str:
        """Get the summary message for the action run."""
        pass
