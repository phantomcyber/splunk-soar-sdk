import json
import base64
import mimetypes

from typing import Optional, TypeVar, Generic, Any, IO, Callable
from pydantic import BaseModel, Field

from soar_sdk.asset import BaseAsset

AssetType = TypeVar("AssetType", bound=BaseAsset)
WebhookHandler = Callable[["WebhookRequest"], "WebhookResponse"]


class WebhookRequest(BaseModel, Generic[AssetType]):
    """Canonical format for HTTP requests made to webhook URLs."""

    method: str
    headers: dict[str, str]
    path_parts: list[str]
    query: dict[str, list[str]]
    body: Optional[str]
    asset: AssetType
    soar_base_url: str
    soar_auth_token: str
    asset_id: int

    @property
    def path(self) -> str:
        """URI path for the request."""
        return "/".join(self.path_parts)


class WebhookResponse(BaseModel):
    """Canonical format for HTTP responses from webhook URLs."""

    status_code: int
    headers: list[tuple[str, str]] = Field(default_factory=list)
    content: str
    is_base64_encoded: bool = False

    def set_header(self, name: str, value: str) -> None:
        """Sets the response header 'name' to value 'value'."""
        for idx, header in enumerate(self.headers):
            if header[0] == name:
                self.headers[idx] = (name, value)
                return

        self.headers.append((name, value))

    def set_headers(self, headers: dict[str, str]) -> None:
        """Bulk set headers from the provided dictionary."""
        for name, value in headers.items():
            self.set_header(name, value)

    def clear_header(self, name: str) -> None:
        """Empty the HTTP response of headers."""
        for idx, header in enumerate(self.headers):
            if header[0] == name:
                self.headers.pop(idx)
                return

        raise IndexError(f"Header not found: {name}")

    @staticmethod
    def text_response(
        content: str,
        status_code: int = 200,
        extra_headers: Optional[dict[str, Any]] = None,
    ) -> "WebhookResponse":
        """Build a WebhookResponse object given raw textual content.

        Produces an HTTP response with a 'text/plain' content type.
        """
        response = WebhookResponse(
            content=content,
            status_code=status_code,
            headers=[("Content-Type", "text/plain")],
        )
        response.set_headers(extra_headers or {})
        return response

    @staticmethod
    def json_response(
        content: dict,
        status_code: int = 200,
        extra_headers: Optional[dict[str, Any]] = None,
    ) -> "WebhookResponse":
        """Build a WebhookResponse object given a dictionary, to be interpreted as JSON.

        Produces an HTTP response with an 'application/json' content type.
        """
        response = WebhookResponse(
            content=json.dumps(content),
            status_code=status_code,
            headers=[("Content-Type", "application/json")],
        )
        response.set_headers(extra_headers or {})
        return response

    @staticmethod
    def file_response(
        fd: IO,
        filename: str,
        content_type: Optional[str] = None,
        status_code: int = 200,
        extra_headers: Optional[dict[str, Any]] = None,
    ) -> "WebhookResponse":
        """Build a webhook response using the data in a given open file-like object.

        Produces an HTTP response with the appropriate content type for the given file,
        based on a buest-guess at the file's MIME type. If the file's MIME type cannot be
        determined, a ValueError will be raised. If the file is open in 'bytes' mode,
        the contents will be base64 encoded in the resulting HTTP response.
        """
        is_base64_encoded = False

        content = fd.read()
        if isinstance(content, bytes):
            content = base64.b64encode(content).decode()
            is_base64_encoded = True

        response = WebhookResponse(
            status_code=status_code,
            content=content,
            is_base64_encoded=is_base64_encoded,
        )

        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)

            if content_type is None:
                raise ValueError(
                    f"Could not determine content type for file: {filename}"
                )

        response.set_header("Content-Type", content_type)
        response.set_header("Content-Disposition", f'attachment; filename="{filename}"')
        response.set_headers(extra_headers or {})
        return response
