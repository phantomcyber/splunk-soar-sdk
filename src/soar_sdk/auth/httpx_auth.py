from __future__ import annotations

import base64
from collections.abc import Generator

import httpx

from soar_sdk.auth.client import SOARAssetOAuthClient
from soar_sdk.auth.models import OAuthToken


class BasicAuth(httpx.Auth):
    """HTTPX authentication using HTTP Basic Authentication."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def auth_flow(
        self,
        request: httpx.Request,
    ) -> Generator[httpx.Request, httpx.Response]:
        """Add Basic authentication header to the request."""
        credentials = f"{self._username}:{self._password}"
        encoded = base64.b64encode(credentials.encode()).decode("ascii")
        request.headers["Authorization"] = f"Basic {encoded}"
        yield request


class StaticTokenAuth(httpx.Auth):
    """HTTPX authentication using a static token."""

    def __init__(
        self,
        token: OAuthToken | str,
        *,
        token_type: str = "Bearer",  # noqa: S107
        header_name: str = "Authorization",
    ) -> None:
        if isinstance(token, str):
            self._access_token = token
        else:
            self._access_token = token.access_token
            token_type = token.token_type or token_type
        self._token_type = token_type
        self._header_name = header_name

    def auth_flow(
        self,
        request: httpx.Request,
    ) -> Generator[httpx.Request, httpx.Response]:
        """Add authentication header to the request."""
        if self._token_type:
            request.headers[self._header_name] = (
                f"{self._token_type} {self._access_token}"
            )
        else:
            request.headers[self._header_name] = self._access_token
        yield request


class OAuthBearerAuth(httpx.Auth):
    """HTTPX authentication using OAuth Bearer tokens."""

    requires_response_body = True

    def __init__(
        self,
        oauth_client: SOARAssetOAuthClient,
        *,
        auto_refresh: bool = True,
    ) -> None:
        self._oauth_client = oauth_client
        self._auto_refresh = auto_refresh
        self._token: OAuthToken | None = None

    def auth_flow(
        self,
        request: httpx.Request,
    ) -> Generator[httpx.Request, httpx.Response]:
        """Handle authentication flow for a request."""
        if self._token is None or self._token.is_expired():
            self._token = self._oauth_client.get_valid_token(
                auto_refresh=self._auto_refresh
            )

        request.headers["Authorization"] = f"Bearer {self._token.access_token}"
        response = yield request

        if (
            response.status_code == 401
            and self._auto_refresh
            and self._token.refresh_token
        ):
            self._token = self._oauth_client.refresh_token(self._token.refresh_token)
            request.headers["Authorization"] = f"Bearer {self._token.access_token}"
            yield request
