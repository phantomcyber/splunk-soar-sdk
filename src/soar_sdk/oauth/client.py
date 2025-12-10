from __future__ import annotations

import secrets
import urllib.parse
import uuid
from typing import TYPE_CHECKING, Any

import httpx
from authlib.integrations.httpx_client import (  # type: ignore[import-untyped]
    OAuth2Client,
)
from authlib.oauth2.rfc7636 import (  # type: ignore[import-untyped]
    create_s256_code_challenge,
)

from soar_sdk.logging import getLogger
from soar_sdk.oauth.models import (
    CertificateCredentials,
    OAuthConfig,
    OAuthGrantType,
    OAuthSession,
    OAuthState,
    OAuthToken,
)

if TYPE_CHECKING:
    from soar_sdk.asset_state import AssetState

logger = getLogger()


class OAuthClientError(Exception):
    """Base exception for OAuth client errors."""


class TokenExpiredError(OAuthClientError):
    """Raised when an access token has expired and cannot be refreshed."""


class AuthorizationRequiredError(OAuthClientError):
    """Raised when user authorization is required to obtain tokens."""


class TokenRefreshError(OAuthClientError):
    """Raised when token refresh fails."""


class ConfigurationChangedError(OAuthClientError):
    """Raised when OAuth client credentials have changed, requiring re-authorization."""


class SOARAssetOAuthClient:
    """OAuth 2.0 client for SOAR asset authentication.

    This client provides a complete OAuth 2.0 implementation that integrates
    with the SOAR SDK's asset state management for secure token persistence.
    It supports multiple grant types including authorization code flow and
    client credentials flow.

    The client uses authlib with httpx for HTTP transport, providing both
    synchronous and asynchronous capabilities with proper timeout and
    error handling.

    Args:
        config: OAuth configuration containing client credentials and endpoints.
        auth_state: SOAR asset state for persisting OAuth tokens securely.
        http_client: Optional httpx client for making HTTP requests. If not
            provided, a new client will be created.
        verify_ssl: Whether to verify SSL certificates. Defaults to True.
        timeout: Request timeout in seconds. Defaults to 30.

    Example:
        >>> config = OAuthConfig(
        ...     client_id="my-client-id",
        ...     client_secret="my-client-secret",
        ...     authorization_endpoint="https://auth.example.com/authorize",
        ...     token_endpoint="https://auth.example.com/token",
        ...     redirect_uri="https://soar.example.com/oauth/callback",
        ...     scope=["read", "write"],
        ... )
        >>> oauth_client = SOARAssetOAuthClient(config, asset.auth_state)
        >>> token = oauth_client.get_valid_token()
    """

    def __init__(
        self,
        config: OAuthConfig,
        auth_state: AssetState,
        *,
        http_client: httpx.Client | None = None,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._auth_state = auth_state
        self._timeout = timeout
        self._verify_ssl = verify_ssl

        self._http_client = http_client or httpx.Client(
            verify=verify_ssl,
            timeout=timeout,
        )

        self._oauth2_client = OAuth2Client(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            scope=config.get_scope_string(),
            token_endpoint=config.token_endpoint,
        )

    @property
    def config(self) -> OAuthConfig:
        """Return the OAuth configuration."""
        return self._config

    def _load_state(self) -> OAuthState:
        """Load OAuth state from asset storage."""
        state_data = self._auth_state.get_all()
        if not state_data:
            return OAuthState()

        oauth_data = state_data.get("oauth")
        if oauth_data is None:
            return OAuthState()

        if isinstance(oauth_data, dict):
            return OAuthState.model_validate(oauth_data)
        return OAuthState()

    def _save_state(self, state: OAuthState) -> None:
        """Save OAuth state to asset storage."""
        current = self._auth_state.get_all()
        current["oauth"] = state.model_dump(mode="json", exclude_none=True)  # type: ignore[assignment]
        self._auth_state.put_all(current)

    def _clear_tokens(self) -> None:
        """Clear stored tokens from auth state."""
        state = self._load_state()
        state.token = None
        self._save_state(state)

    def _check_client_id_changed(self) -> bool:
        """Check if the client_id has changed since tokens were stored."""
        state = self._load_state()
        if state.client_id is None:
            return False
        return state.client_id != self._config.client_id

    def get_stored_token(self) -> OAuthToken | None:
        """Retrieve the stored OAuth token if available.

        Returns:
            The stored OAuthToken or None if no token is stored.

        Raises:
            ConfigurationChangedError: If the client_id has changed since
                the token was stored, indicating re-authorization is needed.
        """
        if self._check_client_id_changed():
            self._clear_tokens()
            raise ConfigurationChangedError(
                "OAuth client credentials have changed. Re-authorization required."
            )

        state = self._load_state()
        return state.token

    def get_valid_token(self, auto_refresh: bool = True) -> OAuthToken:
        """Get a valid access token, refreshing if necessary.

        This method retrieves the stored token and checks if it's still valid.
        If the token is expired and a refresh token is available, it will
        automatically attempt to refresh the token.

        Args:
            auto_refresh: Whether to automatically refresh expired tokens.
                Defaults to True.

        Returns:
            A valid OAuthToken.

        Raises:
            AuthorizationRequiredError: If no token is available or the token
                cannot be refreshed.
            TokenExpiredError: If the token is expired and auto_refresh is False
                or refresh fails.
            ConfigurationChangedError: If client credentials have changed.
        """
        token = self.get_stored_token()

        if token is None:
            raise AuthorizationRequiredError(
                "No OAuth token available. Authorization is required."
            )

        if not token.is_expired():
            return token

        if not auto_refresh:
            raise TokenExpiredError("Access token has expired.")

        if token.refresh_token is None:
            raise TokenExpiredError(
                "Access token has expired and no refresh token is available."
            )

        return self.refresh_token(token.refresh_token)

    def refresh_token(self, refresh_token: str) -> OAuthToken:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token to use.

        Returns:
            A new OAuthToken with updated access token.

        Raises:
            TokenRefreshError: If the refresh request fails.
        """
        try:
            response = self._http_client.post(
                self._config.token_endpoint,
                data={
                    "grant_type": OAuthGrantType.REFRESH_TOKEN.value,
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "refresh_token": refresh_token,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_body = e.response.json()
                error_detail = error_body.get("error_description", str(error_body))
            except Exception:
                error_detail = e.response.text

            raise TokenRefreshError(f"Token refresh failed: {error_detail}") from e

        except httpx.RequestError as e:
            raise TokenRefreshError(f"Token refresh request failed: {e}") from e

        if "refresh_token" not in token_data:
            token_data["refresh_token"] = refresh_token

        new_token = OAuthToken.model_validate(token_data)
        self._store_token(new_token)

        return new_token

    def _store_token(self, token: OAuthToken) -> None:
        """Store a token in the auth state."""
        state = self._load_state()
        state.token = token
        state.client_id = self._config.client_id
        self._save_state(state)

    def fetch_token_with_client_credentials(
        self,
        *,
        extra_params: dict[str, Any] | None = None,
    ) -> OAuthToken:
        """Fetch an access token using client credentials grant.

        This flow is used for server-to-server authentication where no
        user interaction is required.

        Args:
            extra_params: Additional parameters to include in the token request.

        Returns:
            The obtained OAuthToken.

        Raises:
            OAuthClientError: If the token request fails.
        """
        data: dict[str, Any] = {
            "grant_type": OAuthGrantType.CLIENT_CREDENTIALS.value,
            "client_id": self._config.client_id,
        }

        if self._config.client_secret:
            data["client_secret"] = self._config.client_secret

        scope = self._config.get_scope_string()
        if scope:
            data["scope"] = scope

        if extra_params:
            data.update(extra_params)

        try:
            response = self._http_client.post(
                self._config.token_endpoint,
                data=data,
                timeout=self._timeout,
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_detail = self._extract_error_detail(e.response)
            raise OAuthClientError(
                f"Client credentials token request failed: {error_detail}"
            ) from e

        except httpx.RequestError as e:
            raise OAuthClientError(
                f"Client credentials token request failed: {e}"
            ) from e

        token = OAuthToken.model_validate(token_data)
        self._store_token(token)

        return token

    def create_authorization_url(
        self,
        asset_id: str,
        *,
        use_pkce: bool = True,
        extra_params: dict[str, Any] | None = None,
    ) -> tuple[str, OAuthSession]:
        """Create an authorization URL for the authorization code flow.

        This method generates a URL that the user should be redirected to
        in order to authorize the application. It also creates a session
        object to track the authorization state.

        Args:
            asset_id: The SOAR asset ID, used to correlate the callback.
            use_pkce: Whether to use PKCE (Proof Key for Code Exchange) for
                enhanced security. Defaults to True.
            extra_params: Additional parameters to include in the authorization URL.

        Returns:
            A tuple of (authorization_url, session) where session contains
            the state needed to complete the authorization.

        Raises:
            OAuthClientError: If authorization_endpoint is not configured.
        """
        if not self._config.authorization_endpoint:
            raise OAuthClientError(
                "authorization_endpoint is required for authorization code flow"
            )

        session_id = str(uuid.uuid4())
        state_value = urllib.parse.urlencode(
            {
                "asset_id": asset_id,
                "session_id": session_id,
            }
        )

        session = OAuthSession(
            session_id=session_id,
            asset_id=asset_id,
            state=state_value,
            auth_pending=True,
            auth_complete=False,
        )

        params: dict[str, Any] = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "state": state_value,
        }

        if self._config.redirect_uri:
            params["redirect_uri"] = self._config.redirect_uri

        scope = self._config.get_scope_string()
        if scope:
            params["scope"] = scope

        if use_pkce:
            code_verifier = secrets.token_urlsafe(32)
            code_challenge = create_s256_code_challenge(code_verifier)
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            session.code_verifier = code_verifier

        if extra_params:
            params.update(extra_params)

        auth_url = (
            f"{self._config.authorization_endpoint}?{urllib.parse.urlencode(params)}"
        )

        state = self._load_state()
        state.session = session
        self._save_state(state)

        return auth_url, session

    def fetch_token_with_authorization_code(
        self,
        code: str,
        *,
        code_verifier: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> OAuthToken:
        """Exchange an authorization code for an access token.

        Args:
            code: The authorization code received from the authorization callback.
            code_verifier: The PKCE code verifier if PKCE was used during
                authorization. If not provided, attempts to retrieve from session.
            extra_params: Additional parameters to include in the token request.

        Returns:
            The obtained OAuthToken.

        Raises:
            OAuthClientError: If the token exchange fails.
        """
        state = self._load_state()
        session = state.session

        if code_verifier is None and session and session.code_verifier:
            code_verifier = session.code_verifier

        data: dict[str, Any] = {
            "grant_type": OAuthGrantType.AUTHORIZATION_CODE.value,
            "client_id": self._config.client_id,
            "code": code,
        }

        if self._config.client_secret:
            data["client_secret"] = self._config.client_secret

        if self._config.redirect_uri:
            data["redirect_uri"] = self._config.redirect_uri

        if code_verifier:
            data["code_verifier"] = code_verifier

        if extra_params:
            data.update(extra_params)

        try:
            response = self._http_client.post(
                self._config.token_endpoint,
                data=data,
                timeout=self._timeout,
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_detail = self._extract_error_detail(e.response)
            raise OAuthClientError(
                f"Authorization code exchange failed: {error_detail}"
            ) from e

        except httpx.RequestError as e:
            raise OAuthClientError(
                f"Authorization code exchange request failed: {e}"
            ) from e

        token = OAuthToken.model_validate(token_data)
        self._store_token(token)

        state.session = None
        self._save_state(state)

        return token

    def handle_authorization_callback(
        self,
        callback_params: dict[str, str],
    ) -> OAuthToken:
        """Handle the OAuth authorization callback.

        This method processes the callback from the authorization server,
        validates the state parameter, and exchanges the authorization
        code for tokens.

        Args:
            callback_params: The query parameters from the callback URL.

        Returns:
            The obtained OAuthToken.

        Raises:
            OAuthClientError: If the callback indicates an error or state
                validation fails.
        """
        if "error" in callback_params:
            error = callback_params.get("error", "unknown_error")
            error_description = callback_params.get(
                "error_description", "No description provided"
            )
            raise OAuthClientError(
                f"Authorization failed: {error} - {error_description}"
            )

        code = callback_params.get("code")
        if not code:
            raise OAuthClientError("No authorization code in callback")

        callback_state = callback_params.get("state")
        if callback_state:
            state = self._load_state()
            if state.session and state.session.state != callback_state:
                raise OAuthClientError("State mismatch in authorization callback")

        return self.fetch_token_with_authorization_code(code)

    def get_pending_session(self) -> OAuthSession | None:
        """Get the current pending authorization session if any.

        Returns:
            The pending OAuthSession or None if no session is pending.
        """
        state = self._load_state()
        if state.session and state.session.auth_pending:
            return state.session
        return None

    def complete_session(
        self,
        session_id: str,
        *,
        auth_code: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> None:
        """Mark an authorization session as complete.

        This method is called from the webhook handler when the authorization
        callback is received.

        Args:
            session_id: The session ID to complete.
            auth_code: The authorization code if successful.
            error: Error code if authorization failed.
            error_description: Error description if authorization failed.
        """
        state = self._load_state()
        if state.session is None or state.session.session_id != session_id:
            return

        state.session.auth_pending = False
        state.session.auth_complete = error is None
        state.session.auth_code = auth_code
        state.session.error = error
        state.session.error_description = error_description

        self._save_state(state)

    def set_authorization_code(self, code: str) -> None:
        """Store an authorization code in the current session."""
        state = self._load_state()
        if state.session:
            state.session.auth_code = code
            state.session.auth_pending = False
            state.session.auth_complete = True
            self._save_state(state)

    def get_authorization_code(self, *, force_reload: bool = False) -> str | None:
        """Retrieve the authorization code from the current session."""
        if force_reload:
            self._auth_state.get_all(force_reload=True)
        state = self._load_state()
        if state.session and state.session.auth_complete:
            return state.session.auth_code
        return None

    def clear_session(self) -> None:
        """Clear the current authorization session."""
        state = self._load_state()
        state.session = None
        self._save_state(state)

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Extract error details from an HTTP response."""
        try:
            error_body = response.json()
            if isinstance(error_body, dict):
                if "error_description" in error_body:
                    return str(error_body["error_description"])
                if "error" in error_body:
                    return str(error_body["error"])
            return str(error_body)
        except Exception:
            return response.text or f"HTTP {response.status_code}"


class CertificateOAuthClient(SOARAssetOAuthClient):
    """OAuth client for certificate-based authentication.

    This client extends SOARAssetOAuthClient to support OAuth 2.0 Client
    Credentials flow using a certificate for authentication instead of
    a client secret.
    """

    def __init__(
        self,
        config: OAuthConfig,
        auth_state: AssetState,
        certificate: CertificateCredentials,
        *,
        http_client: httpx.Client | None = None,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            config,
            auth_state,
            http_client=http_client,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._certificate = certificate

    def fetch_token_with_certificate(
        self,
        *,
        extra_params: dict[str, Any] | None = None,
    ) -> OAuthToken:
        """Fetch an access token using certificate-based client credentials.

        This method implements the OAuth 2.0 Client Credentials flow using
        a client assertion (JWT signed with the certificate private key)
        for authentication.

        Args:
            extra_params: Additional parameters to include in the token request.

        Returns:
            The obtained OAuthToken.

        Raises:
            OAuthClientError: If the token request fails.
        """
        import time

        import jwt

        now = int(time.time())
        jwt_payload = {
            "aud": self._config.token_endpoint,
            "iss": self._config.client_id,
            "sub": self._config.client_id,
            "exp": now + 300,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        headers = {
            "alg": "RS256",
            "typ": "JWT",
            "x5t": self._certificate.certificate_thumbprint,
        }

        client_assertion = jwt.encode(
            jwt_payload,
            self._certificate.private_key,
            algorithm="RS256",
            headers=headers,
        )

        data: dict[str, Any] = {
            "grant_type": OAuthGrantType.CLIENT_CREDENTIALS.value,
            "client_id": self._config.client_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion,
        }

        scope = self._config.get_scope_string()
        if scope:
            data["scope"] = scope

        if extra_params:
            data.update(extra_params)

        try:
            response = self._http_client.post(
                self._config.token_endpoint,
                data=data,
                timeout=self._timeout,
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_detail = self._extract_error_detail(e.response)
            raise OAuthClientError(
                f"Certificate-based token request failed: {error_detail}"
            ) from e

        except httpx.RequestError as e:
            raise OAuthClientError(
                f"Certificate-based token request failed: {e}"
            ) from e

        token = OAuthToken.model_validate(token_data)
        self._store_token(token)

        return token
