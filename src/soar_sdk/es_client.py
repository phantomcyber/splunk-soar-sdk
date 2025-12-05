import httpx
from httpx_retries import Retry, RetryTransport
from httpx_retries.retry import HTTPMethod, HTTPStatus

from soar_sdk.apis.es.findings import Findings

RETRYABLE_METHODS = [
    HTTPMethod.GET,
    HTTPMethod.PUT,
    HTTPMethod.POST,
    HTTPMethod.PATCH,
    HTTPMethod.DELETE,
]
RETRYABLE_STATUSES = [
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
]


class ESClient:
    """A client for accessing Splunk Enterprise Security APIs."""

    def __init__(self, base_url: str, session_key: str, verify: bool = True) -> None:
        transport = RetryTransport(
            transport=httpx.HTTPTransport(verify=verify),
            retry=Retry(
                allowed_methods=RETRYABLE_METHODS,
                status_forcelist=RETRYABLE_STATUSES,
                total=5,
            ),
        )
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            headers={"Authorization": f"Splunk {session_key}"},
        )

    @property
    def findings(self) -> Findings:
        """The ES /public/v2/findings API."""
        return Findings(self._client)
