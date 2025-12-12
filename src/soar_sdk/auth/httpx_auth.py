"""HTTPX authentication handlers."""

from __future__ import annotations

import base64
from collections.abc import Generator

import httpx

from soar_sdk.auth.client import SOARAssetOAuthClient
from soar_sdk.auth.models import OAuthToken


class BasicAuth(httpx.Auth):
    """HTTPX authentication using HTTP Basic Authentication.

    Args:
        username: The username.
        password: The password.

    Example:
        >>> auth = BasicAuth(asset.username, asset.password)
        >>> with httpx.Client(auth=auth) as client:
        ...     response = client.get("https://api.example.com/data")
    """

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
    """HTTPX authentication using a static token.

    Use this when you have a pre-obtained token (API key, bearer token, etc.)
    that doesn't require refresh logic.

    Args:
        token: The token string or OAuthToken object.
        token_type: The token type for the Authorization header. Defaults to "Bearer".

    Example:
        >>> auth = StaticTokenAuth(asset.api_key)
        >>> with httpx.Client(auth=auth) as client:
        ...     response = client.get("https://api.example.com/data")
    """

    def __init__(
        self,
        token: OAuthToken | str,
        *,
        token_type: str = "Bearer",  # noqa: S107
    ) -> None:
        if isinstance(token, str):
            self._access_token = token
        else:
            self._access_token = token.access_token
            token_type = token.token_type or token_type
        self._token_type = token_type

    def auth_flow(
        self,
        request: httpx.Request,
    ) -> Generator[httpx.Request, httpx.Response]:
        """Add authentication header to the request."""
        request.headers["Authorization"] = f"{self._token_type} {self._access_token}"
        yield request


class OAuthBearerAuth(httpx.Auth):
    """HTTPX authentication using OAuth Bearer tokens.

    This auth handler automatically injects the OAuth access token into
    request headers and can optionally refresh expired tokens.

    Args:
        oauth_client: The SOAR OAuth client for token management.
        auto_refresh: Whether to automatically refresh expired tokens.
            Defaults to True.

    Example:
        >>> oauth_client = SOARAssetOAuthClient(config, auth_state)
        >>> auth = OAuthBearerAuth(oauth_client)
        >>> response = httpx.get("https://api.example.com/data", auth=auth)
    """

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
