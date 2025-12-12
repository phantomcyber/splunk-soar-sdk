"""HTTPX authentication integration for OAuth tokens.

This module provides httpx.Auth implementations that integrate with
the SOAR SDK's OAuth client, enabling automatic token injection and
refresh for HTTP requests.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx

from soar_sdk.oauth.client import AuthorizationRequiredError, SOARAssetOAuthClient
from soar_sdk.oauth.models import OAuthToken


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
        """Handle authentication flow for a request.

        This method is called by httpx for each request. It retrieves
        a valid token and adds it to the request headers. If the response
        indicates an authentication failure and auto_refresh is enabled,
        it will attempt to refresh the token and retry.

        Args:
            request: The outgoing HTTP request.

        Yields:
            The authenticated request.
        """
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


class StaticTokenAuth(httpx.Auth):
    """HTTPX authentication using a static token.

    This auth handler uses a pre-obtained token without automatic
    refresh capabilities. Useful when token management is handled
    externally.

    Args:
        token: The OAuth token to use for authentication.
        token_type: The token type for the Authorization header.
            Defaults to "Bearer".

    Example:
        >>> token = OAuthToken(access_token="my-token")
        >>> auth = StaticTokenAuth(token)
        >>> response = httpx.get("https://api.example.com/data", auth=auth)
    """

    _DEFAULT_TOKEN_TYPE = "Bearer"  # noqa: S105

    def __init__(
        self,
        token: OAuthToken | str,
        *,
        token_type: str = _DEFAULT_TOKEN_TYPE,
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
        """Add authentication header to the request.

        Args:
            request: The outgoing HTTP request.

        Yields:
            The authenticated request.
        """
        request.headers["Authorization"] = f"{self._token_type} {self._access_token}"
        yield request


class OAuthClientCredentialsAuth(httpx.Auth):
    """HTTPX authentication using OAuth Client Credentials flow.

    This auth handler automatically obtains and refreshes access tokens
    using the client credentials grant. Since client credentials flow
    doesn't provide refresh tokens, a new access token is obtained
    when the current one expires.

    Args:
        oauth_client: The SOAR OAuth client for token management.
        token_leeway: Number of seconds before expiration to consider
            the token expired. Defaults to 60.

    Example:
        >>> config = OAuthConfig(
        ...     client_id="my-client",
        ...     client_secret="secret",
        ...     token_endpoint="https://auth.example.com/token",
        ... )
        >>> oauth_client = SOARAssetOAuthClient(config, auth_state)
        >>> auth = OAuthClientCredentialsAuth(oauth_client)
        >>> response = httpx.get("https://api.example.com/data", auth=auth)
    """

    requires_response_body = True

    def __init__(
        self,
        oauth_client: SOARAssetOAuthClient,
        *,
        token_leeway: int = 60,
    ) -> None:
        self._oauth_client = oauth_client
        self._token_leeway = token_leeway
        self._token: OAuthToken | None = None

    def _ensure_token(self) -> OAuthToken:
        """Ensure a valid token is available."""
        if self._token is None or self._token.is_expired(leeway=self._token_leeway):
            try:
                self._token = self._oauth_client.get_valid_token(auto_refresh=False)
            except (AuthorizationRequiredError, Exception):
                self._token = self._oauth_client.fetch_token_with_client_credentials()
        return self._token

    def auth_flow(
        self,
        request: httpx.Request,
    ) -> Generator[httpx.Request, httpx.Response]:
        """Handle authentication flow for a request.

        Args:
            request: The outgoing HTTP request.

        Yields:
            The authenticated request.
        """
        token = self._ensure_token()
        request.headers["Authorization"] = f"Bearer {token.access_token}"
        response = yield request

        if response.status_code == 401:
            self._token = self._oauth_client.fetch_token_with_client_credentials()
            request.headers["Authorization"] = f"Bearer {self._token.access_token}"
            yield request


def create_oauth_auth(
    oauth_client: SOARAssetOAuthClient,
    *,
    auto_refresh: bool = True,
) -> OAuthBearerAuth:
    """Create an httpx.Auth instance for OAuth authentication.

    This is a convenience factory function for creating the appropriate
    auth handler based on the OAuth configuration.

    Args:
        oauth_client: The SOAR OAuth client.
        auto_refresh: Whether to automatically refresh expired tokens.

    Returns:
        An httpx.Auth instance configured for OAuth.

    Example:
        >>> auth = create_oauth_auth(oauth_client)
        >>> client = httpx.Client(auth=auth)
    """
    return OAuthBearerAuth(oauth_client, auto_refresh=auto_refresh)
