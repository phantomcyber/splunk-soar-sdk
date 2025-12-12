from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from soar_sdk.auth.client import (
    AuthorizationRequiredError,
    OAuthClientError,
    SOARAssetOAuthClient,
    TokenExpiredError,
)
from soar_sdk.auth.models import OAuthConfig, OAuthGrantType, OAuthToken
from soar_sdk.logging import getLogger

if TYPE_CHECKING:
    from soar_sdk.asset_state import AssetState

logger = getLogger()


class OAuthFlow(ABC):
    """Abstract base class for OAuth authentication flows."""

    @abstractmethod
    def authenticate(self) -> OAuthToken:
        """Execute the authentication flow and return a valid token."""

    @abstractmethod
    def get_token(self) -> OAuthToken:
        """Get a valid token, refreshing if necessary."""


class ClientCredentialsFlow(OAuthFlow):
    """OAuth 2.0 Client Credentials flow."""

    def __init__(
        self,
        auth_state: AssetState,
        *,
        client_id: str,
        client_secret: str,
        token_endpoint: str,
        scope: str | list[str] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        self._auth_state = auth_state
        self._extra_params = extra_params

        self._config = OAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=token_endpoint,
            scope=scope,
            grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
        )

        self._client = SOARAssetOAuthClient(self._config, auth_state)

    def authenticate(self) -> OAuthToken:
        """Authenticate using client credentials."""
        return self._client.fetch_token_with_client_credentials(
            extra_params=self._extra_params,
        )

    def get_token(self) -> OAuthToken:
        """Get a valid token, fetching a new one if expired."""
        try:
            return self._client.get_valid_token(auto_refresh=False)
        except (AuthorizationRequiredError, TokenExpiredError):
            return self.authenticate()


class AuthorizationCodeFlow(OAuthFlow):
    """OAuth 2.0 Authorization Code flow."""

    def __init__(
        self,
        auth_state: AssetState,
        asset_id: str,
        *,
        client_id: str,
        client_secret: str | None = None,
        authorization_endpoint: str,
        token_endpoint: str,
        redirect_uri: str,
        scope: str | list[str] | None = None,
        use_pkce: bool = False,
        extra_auth_params: dict[str, Any] | None = None,
        extra_token_params: dict[str, Any] | None = None,
        poll_timeout: int = 300,
        poll_interval: int = 3,
    ) -> None:
        self._auth_state = auth_state
        self._asset_id = asset_id
        self._use_pkce = use_pkce
        self._extra_auth_params = extra_auth_params
        self._extra_token_params = extra_token_params
        self._poll_timeout = poll_timeout
        self._poll_interval = poll_interval

        self._config = OAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            redirect_uri=redirect_uri,
            scope=scope,
            grant_type=OAuthGrantType.AUTHORIZATION_CODE,
        )

        self._client = SOARAssetOAuthClient(self._config, auth_state)

    @property
    def client(self) -> SOARAssetOAuthClient:
        """Return the OAuth client."""
        return self._client

    def get_authorization_url(self) -> str:
        """Generate the authorization URL."""
        auth_url, _ = self._client.create_authorization_url(
            self._asset_id,
            use_pkce=self._use_pkce,
            extra_params=self._extra_auth_params,
        )
        return auth_url

    def set_authorization_code(self, code: str) -> None:
        """Store authorization code in state (called by webhook)."""
        self._client.set_authorization_code(code)

    def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange an authorization code for tokens."""
        return self._client.fetch_token_with_authorization_code(
            code,
            extra_params=self._extra_token_params,
        )

    def wait_for_authorization(
        self,
        on_progress: Callable[[int], None] | None = None,
    ) -> OAuthToken:
        """Wait for user authorization to complete by polling state."""
        start_time = time.time()
        iteration = 0

        while time.time() - start_time < self._poll_timeout:
            time.sleep(self._poll_interval)
            iteration += 1

            if on_progress:
                on_progress(iteration)

            code = self._client.get_authorization_code(force_reload=True)
            if code:
                return self.exchange_code_for_token(code)

        raise OAuthClientError(
            f"Authorization timed out after {self._poll_timeout} seconds"
        )

    def authenticate(self) -> OAuthToken:
        """Execute the full authorization code flow."""
        auth_url = self.get_authorization_url()
        raise AuthorizationRequiredError(
            f"User authorization required. Please visit: {auth_url}"
        )

    def get_token(self) -> OAuthToken:
        """Get a valid token, refreshing if necessary."""
        return self._client.get_valid_token(auto_refresh=True)
