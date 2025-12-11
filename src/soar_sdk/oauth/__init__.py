"""OAuth 2.0 authentication for SOAR connectors."""

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
