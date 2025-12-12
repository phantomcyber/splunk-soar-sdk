from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OAuthGrantType(StrEnum):
    """Supported OAuth 2.0 grant types."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"  # noqa: S105


class OAuthToken(BaseModel):
    """OAuth 2.0 token response."""

    model_config = ConfigDict(extra="allow")

    _DEFAULT_TOKEN_TYPE = "Bearer"  # noqa: S105

    access_token: str
    token_type: str = _DEFAULT_TOKEN_TYPE
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    expires_at: float | None = None

    def model_post_init(self, __context: object) -> None:
        """Calculate expires_at if not provided but expires_in is available."""
        if self.expires_at is None and self.expires_in is not None:
            self.expires_at = time.time() + self.expires_in

    def is_expired(self, leeway: int = 30) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        return time.time() >= (self.expires_at - leeway)


class OAuthConfig(BaseModel):
    """Configuration for OAuth 2.0 authentication."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str
    redirect_uri: str | None = None
    scope: str | list[str] | None = None
    grant_type: OAuthGrantType = OAuthGrantType.AUTHORIZATION_CODE

    def get_scope_string(self) -> str | None:
        """Return scope as a space-separated string."""
        if self.scope is None:
            return None
        if isinstance(self.scope, list):
            return " ".join(self.scope)
        return self.scope


class OAuthSession(BaseModel):
    """Represents an active OAuth authentication session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    asset_id: str
    auth_pending: bool = True
    auth_complete: bool = False
    auth_code: str | None = None
    error: str | None = None
    error_description: str | None = None
    state: str | None = None
    code_verifier: str | None = None


class OAuthState(BaseModel):
    """State persisted in auth_state for OAuth authentication."""

    model_config = ConfigDict(extra="forbid")

    token: OAuthToken | None = None
    session: OAuthSession | None = None
    client_id: str | None = Field(
        default=None,
        description="Stored client_id to detect credential changes",
    )


class CertificateCredentials(BaseModel):
    """Certificate-based authentication credentials."""

    model_config = ConfigDict(extra="forbid")

    certificate_thumbprint: str
    private_key: str
    tenant_id: str | None = None
