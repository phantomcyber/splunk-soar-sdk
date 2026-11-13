"""Direct ES public findings calls without shared SOAR authentication."""

__lazy_modules__ = {
    "collections.abc",
    "contextlib",
    "httpx",
    "importlib",
    "json",
    "pydantic",
    "soar_sdk.exceptions",
    "soar_sdk.models.es_finding",
    "typing",
    "urllib.parse",
}

import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from importlib import import_module
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr, ValidationError

from soar_sdk.exceptions import (
    FindingAPIError,
    FindingAuthorizationError,
    FindingConfigurationError,
    FindingRateLimitError,
    FindingTimeoutError,
    FindingUnavailableError,
    FindingValidationError,
)
from soar_sdk.models.es_finding import (
    CreateFindingRequest,
    CreateFindingResponse,
    FindingCreateResult,
)


def _get_runtime_es_context() -> tuple[str, str | SecretStr] | None:
    """Read the bundle-owned context on demand; classic SOAR has no bridge."""
    bridge = None
    try:
        bridge = import_module("es_poll_api")
    except ModuleNotFoundError as error:
        if error.name == "es_poll_api":
            return None
    except Exception:
        bridge = None
    if bridge is None:
        raise FindingConfigurationError("ES polling runtime could not be loaded.")
    context = False
    with suppress(Exception):
        context = bridge.get_es_context()
    if context is False:
        raise FindingConfigurationError(
            "ES polling requires an execution URL and token."
        )
    return cast(tuple[str, str | SecretStr] | None, context)


def _normalize_legacy_finding(
    finding: CreateFindingRequest | Mapping[str, Any],
) -> CreateFindingRequest | Mapping[str, Any]:
    """Adapt existing Finding dictionaries without changing the caller's data."""
    if not isinstance(finding, Mapping):
        return finding
    payload = dict(finding)
    additional_fields = payload.get("additional_fields")
    if isinstance(additional_fields, Mapping):
        payload["additional_fields"] = [
            {"name": name, "value": value} for name, value in additional_fields.items()
        ]
    email = payload.get("email")
    if isinstance(email, Mapping):
        reporter = email.get("reporter")
        if isinstance(reporter, Mapping):
            normalized_reporter = dict(reporter)
            for field in ("to", "cc", "bcc"):
                if isinstance(reporter.get(field), str):
                    normalized_reporter[field] = [reporter[field]]
            payload["email"] = {**email, "reporter": normalized_reporter}
    return payload


def _create_es_finding(
    finding: CreateFindingRequest | Mapping[str, Any],
    *,
    base_url: str,
    token: str | SecretStr,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Create one finding and return the validated ES response dictionary.

    Args:
        finding: ES request model or serialized Finding. Legacy reporter
            recipients and additional fields are adapted to the ES wire format.
        base_url: ES stack origin or OpenAPI server URL, including its namespace
            prefix when already present. The SDK supplies the namespace for an origin.
        token: Execution-scoped ES bearer token from automationOrchestrator.
            Used only for this call, never stored on the API instance.
        timeout: Positive HTTP timeout in seconds; defaults to 30.

    Raises:
        FindingValidationError: Invalid payload or ES validation rejection.
        FindingConfigurationError: Invalid URL, token, or timeout.
        FindingAuthorizationError: ES returned 401 or 403.
        FindingRateLimitError: ES returned 429.
        FindingTimeoutError: ES timed out; creation may have completed.
        FindingUnavailableError: Transport failure or ES returned 5xx.
        FindingAPIError: Unexpected status or invalid ES success response.
    """
    payload = None
    with suppress(ValueError):
        # Serialize before transport so malformed text is a per-finding validation
        # failure, rather than an encoding exception that aborts the whole batch.
        payload = CreateFindingRequest.model_validate(
            _normalize_legacy_finding(finding)
        ).model_dump_json(by_alias=True, exclude_none=True)
    if payload is None:
        raise FindingValidationError("Invalid ES finding payload.")

    secret = token.get_secret_value() if isinstance(token, SecretStr) else token
    url = None
    with suppress(TypeError, ValueError, httpx.InvalidURL):
        urlsplit(base_url)
        url = httpx.URL(base_url)
    if (
        url is None
        or url.scheme not in {"https", "http"}
        or not url.host
        or url.userinfo
        or url.query
        or url.fragment
        or not isinstance(secret, str)
        or not secret
        or any(character.isspace() or not character.isascii() for character in secret)
        or secret in str(url)
        or not isinstance(timeout, int | float)
        or not 0 < timeout < float("inf")
    ):
        raise FindingConfigurationError("Invalid ES URL, token, or timeout.")

    if url.path in {"", "/"}:
        url = url.copy_with(path="/servicesNS/nobody/missioncontrol")
    endpoint = str(url).rstrip("/") + "/public/v2/findings"
    response = None
    failure = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(
                endpoint,
                content=payload,
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException:
        failure = FindingTimeoutError("ES finding creation timed out.")
    except httpx.RequestError:
        failure = FindingUnavailableError("ES finding service is unavailable.")
    # Raise outside the handlers: neither cause nor context retains an
    # upstream exception that could include credentials or response bodies.
    if failure is not None:
        raise failure
    response = cast(httpx.Response, response)

    status = response.status_code
    if status in {401, 403}:
        raise FindingAuthorizationError("ES authorization failed.", status_code=status)
    if status == 429:
        raise FindingRateLimitError("ES rate limit exceeded.", status_code=status)
    if 400 <= status < 500:
        raise FindingValidationError(
            "ES rejected the finding request.", status_code=status
        )
    if 500 <= status < 600:
        raise FindingUnavailableError(
            "ES finding service is unavailable.", status_code=status
        )
    if status != 201:
        raise FindingAPIError(
            "Unexpected ES finding response status.", status_code=status
        )

    created = None
    with suppress(ValidationError):
        created = CreateFindingResponse.model_validate_json(response.content)
    if (
        created is None
        or not created.finding_id.strip()
        or secret in created.finding_id
    ):
        raise FindingAPIError(
            "Invalid ES finding creation response.", status_code=status
        )
    result = created.model_dump(mode="json", by_alias=True, exclude_none=True)
    # Check decoded, normalized response values before returning any fields.
    if json.dumps(secret, ensure_ascii=False)[1:-1] in json.dumps(
        result, ensure_ascii=False
    ):
        raise FindingAPIError(
            "Invalid ES finding creation response.", status_code=status
        )
    return result


def _create_es_findings_bulk(
    findings: Sequence[Mapping[str, Any]], *, base_url: str, token: str | SecretStr
) -> dict[str, Any]:
    """Use single POSTs and preserve the classic bulk envelope with ordered results."""
    results = []
    # ES /public/v2/findings/bulk_create returns successful IDs without input
    # indexes. Its handler groups ordinary and suppressed findings separately,
    # so the returned IDs can be reordered. Use one POST per finding to preserve
    # its identity for attachment linking. Switch to ES bulk only after it returns
    # indexed successes or guarantees that successful IDs retain input order.
    for index, finding in enumerate(findings):
        try:
            response = _create_es_finding(finding, base_url=base_url, token=token)
        except FindingAPIError as error:
            results.append(
                FindingCreateResult(
                    index=index,
                    error_code=error.error_code,
                    message=error.message,
                    status_code=error.status_code,
                )
            )
        else:
            results.append(
                FindingCreateResult(index=index, finding_id=response["finding_id"])
            )
    successful = [result.finding_id for result in results if result.success]
    errors = [
        {
            "index": result.index,
            "error": result.message,
            "error_code": result.error_code,
            "status_code": result.status_code,
        }
        for result in results
        if not result.success
    ]
    return {
        "status": "success" if not errors else "partial" if successful else "error",
        "created": len(successful),
        "failed": len(errors),
        "findings": successful,
        "container_ids": [],
        "errors": errors,
        "results": [
            {**result.model_dump(exclude_none=True), "success": result.success}
            for result in results
        ],
    }
