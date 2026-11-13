__lazy_modules__ = {
    "abc",
    "collections.abc",
    "httpx",
    "pydantic",
    "pydantic.dataclasses",
    "soar_sdk.action_results",
    "soar_sdk.apis.artifact",
    "soar_sdk.apis.attachments",
    "soar_sdk.apis.container",
    "soar_sdk.apis._es_findings",
    "soar_sdk.apis.vault",
    "soar_sdk.exceptions",
    "typing",
}

from abc import abstractmethod
from collections.abc import AsyncIterable, Iterable, Mapping
from typing import Any, Generic, TypeVar

import httpx
from pydantic import SecretStr, field_validator
from pydantic.dataclasses import dataclass

from soar_sdk.action_results import ActionOutput
from soar_sdk.apis._es_findings import (
    _create_es_finding,
    _create_es_findings_bulk,
    _get_runtime_es_context,
)
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.attachments import Attachments
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault
from soar_sdk.exceptions import FindingConfigurationError

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

    @property
    def attachments(self) -> Attachments:
        """Object governing attachment records and finding associations.

        Created on first access and reused for the lifetime of the client.
        """
        api: Attachments | None = getattr(self, "_attachments_api", None)
        if api is None:
            api = Attachments()
            self._attachments_api = api
        return api

    @abstractmethod
    def get_executing_container_id(self) -> int:
        """Return the current Container ID passed in the Connector Run Action JSON."""
        pass

    @abstractmethod
    def get_asset_id(self) -> str:
        """Return the current Asset ID passed in the Connector Run Action JSON."""
        pass

    def _get_es_finding_context(self) -> tuple[str, str | SecretStr] | None:
        """Resolve the current execution's ES server URL and token, or classic mode.

        By default this reads the ingestion bundle's lazy es_poll_api bridge.
        Runtime adapters may override it to read execution-scoped action data.
        None selects the classic SOAR proxy. An adapter handling ES ingestion
        must raise FindingConfigurationError when credentials are unavailable,
        rather than returning None and silently falling back to the proxy.
        The SDK does not cache the returned credentials or invent action fields.
        """
        return _get_runtime_es_context()

    MAX_BULK_FINDINGS = 25

    def create_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Create one finding using the execution's configured ES transport.

        The ``finding`` argument should be the serialized form of a
        :class:`~soar_sdk.models.finding.Finding` model — use
        :meth:`~soar_sdk.models.finding.Finding.to_dict` to produce it. Direct ES
        runtimes also accept the serialized public OpenAPI model
        :class:`~soar_sdk.models.es_finding.CreateFindingRequest`. Legacy reporter
        recipient strings and additional-field mappings are adapted internally;
        the classic proxy payload is unchanged.

        Returns the response dictionary, including ``finding_id`` and ``_time``.
        Runtime adapters supply ES URL/token internally; connectors do not pass
        credentials. Classic runtimes retain the SOAR proxy behavior. Direct ES
        calls raise FindingAPIError subclasses and never retry POST requests.

        Example::

            from soar_sdk.models.finding import Finding

            finding = Finding(rule_title="Suspicious Login", security_domain="identity")
            response = soar.create_finding(finding.to_dict())
        """
        es_context = self._get_es_finding_context()
        if es_context is not None:
            base_url, token = es_context
            return _create_es_finding(finding, base_url=base_url, token=token)
        response = self.post(
            "/rest/enterprise_security/findings", json=finding, timeout=30.0
        )
        return response.json()

    def create_findings_bulk(
        self,
        findings: list[dict[str, Any]],
        container_ids: list[int | None] | None = None,
    ) -> dict[str, Any]:
        """Create findings using the execution's configured ES transport.

        Accepts up to 25 findings per call. When ``container_ids`` is provided,
        the backend links pre-existing containers to the created findings
        instead of creating new ones.

        Returns the bulk response containing ``status``, ``created``,
        ``failed``, ``findings`` (list of IDs), ``container_ids``
        (list of SOAR container IDs), and ``errors``.

        Direct ES runtimes issue one POST per finding and additionally return
        ordered ``results`` with input indexes, IDs or safe failure details.
        ES bulk creation can reorder successful IDs without returning their input
        indexes. Separate POSTs preserve the finding-to-attachment mapping until
        ES provides indexed successes or guarantees the successful ID order.
        No SOAR containers are created; ``container_ids`` input is unsupported
        in direct ES mode. Runtime adapters supply credentials internally.
        """
        if len(findings) > self.MAX_BULK_FINDINGS:
            raise ValueError(
                f"Maximum {self.MAX_BULK_FINDINGS} findings per request, got {len(findings)}"
            )
        es_context = self._get_es_finding_context()
        if es_context is not None:
            if container_ids is not None:
                raise FindingConfigurationError(
                    "SOAR container IDs are unsupported for direct ES finding creation."
                )
            base_url, token = es_context
            return _create_es_findings_bulk(findings, base_url=base_url, token=token)
        if not findings:
            return {
                "status": "success",
                "created": 0,
                "failed": 0,
                "findings": [],
                "container_ids": [],
                "errors": [],
            }

        endpoint = "/rest/enterprise_security/findings/bulk_create"
        timeout = max(30.0, len(findings) * 5.0)

        payload: dict[str, Any] | list = findings
        if container_ids is not None:
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
