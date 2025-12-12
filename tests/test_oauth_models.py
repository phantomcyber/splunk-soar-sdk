import time

import pytest
from pydantic import ValidationError

from soar_sdk.auth.models import (
    CertificateCredentials,
    OAuthConfig,
    OAuthGrantType,
    OAuthSession,
    OAuthState,
    OAuthToken,
)


class TestOAuthToken:
    def test_basic_token_creation(self):
        token = OAuthToken(access_token="test_token")
        assert token.access_token == "test_token"
        assert token.token_type == "Bearer"
        assert token.refresh_token is None
        assert token.scope is None

    def test_full_token_creation(self):
        token = OAuthToken(
            access_token="test_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_token",
            scope="read write",
        )
        assert token.access_token == "test_token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.refresh_token == "refresh_token"
        assert token.scope == "read write"

    def test_expires_at_calculated_from_expires_in(self):
        before = time.time()
        token = OAuthToken(access_token="test_token", expires_in=3600)
        after = time.time()

        assert token.expires_at is not None
        assert before + 3600 <= token.expires_at <= after + 3600

    def test_expires_at_not_calculated_when_already_set(self):
        fixed_expires_at = 1700000000.0
        token = OAuthToken(
            access_token="test_token",
            expires_in=3600,
            expires_at=fixed_expires_at,
        )
        assert token.expires_at == fixed_expires_at

    def test_is_expired_false_when_no_expires_at(self):
        token = OAuthToken(access_token="test_token")
        assert token.is_expired() is False

    def test_is_expired_false_when_not_expired(self):
        token = OAuthToken(access_token="test_token", expires_in=3600)
        assert token.is_expired() is False

    def test_is_expired_true_when_expired(self):
        token = OAuthToken(
            access_token="test_token",
            expires_at=time.time() - 100,
        )
        assert token.is_expired() is True

    def test_is_expired_with_default_leeway(self):
        token = OAuthToken(
            access_token="test_token",
            expires_at=time.time() + 20,
        )
        assert token.is_expired() is True  # Within 30s default leeway

    def test_is_expired_with_custom_leeway(self):
        token = OAuthToken(
            access_token="test_token",
            expires_at=time.time() + 20,
        )
        assert token.is_expired(leeway=10) is False
        assert token.is_expired(leeway=30) is True

    def test_extra_fields_allowed(self):
        token = OAuthToken(
            access_token="test_token",
            custom_field="custom_value",
        )
        assert token.access_token == "test_token"
        assert token.model_dump()["custom_field"] == "custom_value"


class TestOAuthConfig:
    def test_minimal_config(self):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
        )
        assert config.client_id == "test_client"
        assert config.token_endpoint == "https://auth.example.com/token"
        assert config.client_secret is None
        assert config.grant_type == OAuthGrantType.AUTHORIZATION_CODE

    def test_full_config(self):
        config = OAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            scope=["read", "write"],
            grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
        )
        assert config.client_id == "test_client"
        assert config.client_secret == "test_secret"
        assert config.authorization_endpoint == "https://auth.example.com/authorize"
        assert config.redirect_uri == "https://app.example.com/callback"
        assert config.scope == ["read", "write"]
        assert config.grant_type == OAuthGrantType.CLIENT_CREDENTIALS

    def test_get_scope_string_with_list(self):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
            scope=["read", "write", "delete"],
        )
        assert config.get_scope_string() == "read write delete"

    def test_get_scope_string_with_string(self):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
            scope="read write",
        )
        assert config.get_scope_string() == "read write"

    def test_get_scope_string_with_none(self):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
        )
        assert config.get_scope_string() is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            OAuthConfig(
                client_id="test_client",
                token_endpoint="https://auth.example.com/token",
                unknown_field="value",
            )


class TestOAuthSession:
    def test_basic_session(self):
        session = OAuthSession(
            session_id="sess-123",
            asset_id="asset-456",
        )
        assert session.session_id == "sess-123"
        assert session.asset_id == "asset-456"
        assert session.auth_pending is True
        assert session.auth_complete is False
        assert session.auth_code is None
        assert session.error is None
        assert session.state is None
        assert session.code_verifier is None

    def test_full_session(self):
        session = OAuthSession(
            session_id="sess-123",
            asset_id="asset-456",
            auth_pending=False,
            auth_complete=True,
            auth_code="auth_code_value",
            error=None,
            error_description=None,
            state="state_value",
            code_verifier="verifier_value",
        )
        assert session.auth_pending is False
        assert session.auth_complete is True
        assert session.auth_code == "auth_code_value"
        assert session.state == "state_value"
        assert session.code_verifier == "verifier_value"

    def test_session_with_error(self):
        session = OAuthSession(
            session_id="sess-123",
            asset_id="asset-456",
            auth_pending=False,
            auth_complete=False,
            error="access_denied",
            error_description="User denied access",
        )
        assert session.error == "access_denied"
        assert session.error_description == "User denied access"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            OAuthSession(
                session_id="sess-123",
                asset_id="asset-456",
                unknown_field="value",
            )


class TestOAuthState:
    def test_empty_state(self):
        state = OAuthState()
        assert state.token is None
        assert state.session is None
        assert state.client_id is None

    def test_state_with_token(self):
        token = OAuthToken(access_token="test_token")
        state = OAuthState(token=token)
        assert state.token is not None
        assert state.token.access_token == "test_token"

    def test_state_with_session(self):
        session = OAuthSession(session_id="sess-123", asset_id="asset-456")
        state = OAuthState(session=session)
        assert state.session is not None
        assert state.session.session_id == "sess-123"

    def test_state_with_client_id(self):
        state = OAuthState(client_id="test_client")
        assert state.client_id == "test_client"

    def test_full_state(self):
        token = OAuthToken(access_token="test_token")
        session = OAuthSession(session_id="sess-123", asset_id="asset-456")
        state = OAuthState(
            token=token,
            session=session,
            client_id="test_client",
        )
        assert state.token is not None
        assert state.session is not None
        assert state.client_id == "test_client"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            OAuthState(unknown_field="value")


class TestOAuthGrantType:
    def test_grant_type_values(self):
        assert OAuthGrantType.AUTHORIZATION_CODE == "authorization_code"
        assert OAuthGrantType.CLIENT_CREDENTIALS == "client_credentials"
        assert OAuthGrantType.REFRESH_TOKEN == "refresh_token"


class TestCertificateCredentials:
    def test_minimal_credentials(self):
        creds = CertificateCredentials(
            certificate_thumbprint="thumbprint123",
            private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
        )
        assert creds.certificate_thumbprint == "thumbprint123"
        assert "BEGIN PRIVATE KEY" in creds.private_key
        assert creds.tenant_id is None

    def test_full_credentials(self):
        creds = CertificateCredentials(
            certificate_thumbprint="thumbprint123",
            private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
            tenant_id="tenant-456",
        )
        assert creds.tenant_id == "tenant-456"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            CertificateCredentials(
                certificate_thumbprint="thumbprint123",
                private_key="key",
                unknown_field="value",
            )
