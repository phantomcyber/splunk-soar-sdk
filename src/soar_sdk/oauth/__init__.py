"""OAuth 2.0 authentication module for the SOAR SDK.

This module provides a comprehensive OAuth 2.0 implementation for SOAR
connectors, supporting multiple grant types and integrating with the
SDK's asset state management for secure token persistence.

Supported OAuth 2.0 flows:
    - Authorization Code flow (with PKCE support)
    - Client Credentials flow
    - Certificate-based authentication

Key Features:
    - Thread-safe session management with unique session IDs
    - Automatic token refresh
    - Secure token storage via asset auth_state
    - Integration with httpx for HTTP authentication
    - Detection of credential changes requiring re-authorization

Usage:
    The module provides several levels of abstraction:

    1. High-level flows for common use cases:
        >>> from soar_sdk.oauth import ClientCredentialsFlow
        >>> flow = ClientCredentialsFlow(
        ...     auth_state=asset.auth_state,
        ...     client_id="my-client",
        ...     client_secret="secret",
        ...     token_endpoint="https://auth.example.com/token",
        ... )
        >>> token = flow.authenticate()

    2. OAuth client for direct token management:
        >>> from soar_sdk.oauth import SOARAssetOAuthClient, OAuthConfig
        >>> config = OAuthConfig(
        ...     client_id="my-client",
        ...     client_secret="secret",
        ...     token_endpoint="https://auth.example.com/token",
        ... )
        >>> client = SOARAssetOAuthClient(config, asset.auth_state)
        >>> token = client.get_valid_token()

    3. HTTPX authentication for automatic token injection:
        >>> from soar_sdk.oauth import OAuthBearerAuth
        >>> auth = OAuthBearerAuth(oauth_client)
        >>> response = httpx.get("https://api.example.com/data", auth=auth)

Example - Authorization Code Flow:
    >>> from soar_sdk.oauth import AuthorizationCodeFlow
    >>>
    >>> flow = AuthorizationCodeFlow(
    ...     auth_state=asset.auth_state,
    ...     asset_id=soar.get_asset_id(),
    ...     client_id=asset.client_id,
    ...     client_secret=asset.client_secret,
    ...     authorization_endpoint=asset.auth_url,
    ...     token_endpoint=asset.token_url,
    ...     redirect_uri=redirect_uri,
    ...     scope=["openid", "profile", "email"],
    ... )
    >>>
    >>> # During test connectivity:
    >>> auth_url = flow.get_authorization_url()
    >>> print(f"Please visit: {auth_url}")
    >>> token = flow.wait_for_authorization()
    >>>
    >>> # During action execution:
    >>> token = flow.get_token()

Example - Client Credentials Flow:
    >>> from soar_sdk.oauth import ClientCredentialsFlow
    >>>
    >>> flow = ClientCredentialsFlow(
    ...     auth_state=asset.auth_state,
    ...     client_id=asset.client_id,
    ...     client_secret=asset.client_secret,
    ...     token_endpoint="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    ...     scope=["https://graph.microsoft.com/.default"],
    ... )
    >>> token = flow.get_token()

Example - Using with HTTPX:
    >>> from soar_sdk.oauth import SOARAssetOAuthClient, OAuthConfig, OAuthBearerAuth
    >>> import httpx
    >>>
    >>> config = OAuthConfig(
    ...     client_id=asset.client_id,
    ...     client_secret=asset.client_secret,
    ...     token_endpoint=asset.token_url,
    ... )
    >>> oauth_client = SOARAssetOAuthClient(config, asset.auth_state)
    >>> auth = OAuthBearerAuth(oauth_client)
    >>>
    >>> with httpx.Client(auth=auth) as client:
    ...     response = client.get("https://api.example.com/resource")
"""

from soar_sdk.oauth.client import (
    AuthorizationRequiredError,
    CertificateOAuthClient,
    ConfigurationChangedError,
    OAuthClientError,
    SOARAssetOAuthClient,
    TokenExpiredError,
    TokenRefreshError,
)
from soar_sdk.oauth.flows import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
    OAuthFlow,
)
from soar_sdk.oauth.httpx_auth import (
    OAuthBearerAuth,
    OAuthClientCredentialsAuth,
    StaticTokenAuth,
    create_oauth_auth,
)
from soar_sdk.oauth.models import (
    CertificateCredentials,
    OAuthConfig,
    OAuthGrantType,
    OAuthSession,
    OAuthState,
    OAuthToken,
)

__all__ = [
    "AuthorizationCodeFlow",
    "AuthorizationRequiredError",
    "CertificateCredentials",
    "CertificateOAuthClient",
    "ClientCredentialsFlow",
    "ConfigurationChangedError",
    "OAuthBearerAuth",
    "OAuthClientCredentialsAuth",
    "OAuthClientError",
    "OAuthConfig",
    "OAuthFlow",
    "OAuthGrantType",
    "OAuthSession",
    "OAuthState",
    "OAuthToken",
    "SOARAssetOAuthClient",
    "StaticTokenAuth",
    "TokenExpiredError",
    "TokenRefreshError",
    "create_oauth_auth",
]
