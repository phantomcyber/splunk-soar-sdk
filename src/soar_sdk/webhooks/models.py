import json
import base64
import mimetypes

from typing import Optional, TypeVar, Generic, Any, IO
from pydantic import BaseModel, Field

from soar_sdk.asset import BaseAsset

Asset = TypeVar("Asset", bound=BaseAsset)


class WebhookRequest(BaseModel, Generic[Asset]):
    method: str
    headers: dict[str, str]
    path_parts: list[str]
    query: dict[str, str]
    body: Optional[str]
    asset: Asset
    soar_base_url: str
    soar_auth_token: str
    asset_id: int

    @property
    def path(self) -> str:
        return "/".join(self.path_parts)


class WebhookResponse(BaseModel):
    status_code: int
    headers: list[tuple[str, str]] = Field(default_factory=list)
    content: str
    is_base64_encoded: bool = False

    def set_header(self, name: str, value: str) -> None:
        for idx, header in enumerate(self.headers):
            if header[0] == name:
                self.headers[idx] = (name, value)
                return

        self.headers.append((name, value))

    def clear_header(self, name: str) -> None:
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
        response = WebhookResponse(
            content=content,
            status_code=status_code,
            headers=[("Content-Type", "text/plain")],
        )

        extra_headers = extra_headers or {}
        for name, value in extra_headers.items():
            response.set_header(name, value)

        return response

    @staticmethod
    def json_response(
        content: dict,
        status_code: int = 200,
        extra_headers: Optional[dict[str, Any]] = None,
    ) -> "WebhookResponse":
        response = WebhookResponse(
            content=json.dumps(content),
            status_code=status_code,
            headers=[("Content-Type", "application/json")],
        )

        extra_headers = extra_headers or {}
        for name, value in extra_headers.items():
            response.set_header(name, value)

        return response

    @staticmethod
    def file_response(
        fd: IO,
        filename: str,
        content_type: Optional[str] = None,
        status_code: int = 200,
        extra_headers: Optional[dict[str, Any]] = None,
    ) -> "WebhookResponse":
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

        if extra_headers is not None:
            for name, value in extra_headers.items():
                response.set_header(name, value)

        return response
