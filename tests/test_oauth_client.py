import time

import httpx
import pytest
import respx

from soar_sdk.auth.client import (
    AuthorizationRequiredError,
    ConfigurationChangedError,
    OAuthClientError,
    SOARAssetOAuthClient,
    TokenExpiredError,
    TokenRefreshError,
)
from soar_sdk.auth.models import OAuthConfig, OAuthState, OAuthToken


@pytest.fixture
def mock_auth_state():
    class MockAuthState:
        def __init__(self):
            self._data = {}

        def get_all(self, *, force_reload=False):
            return self._data

        def put_all(self, data):
            self._data = dict(data)

    return MockAuthState()


@pytest.fixture
def oauth_config():
    return OAuthConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
        redirect_uri="https://app.example.com/callback",
        scope=["read", "write"],
    )


@pytest.fixture
def oauth_client(oauth_config, mock_auth_state):
    return SOARAssetOAuthClient(oauth_config, mock_auth_state)


class TestSOARAssetOAuthClientInit:
    def test_client_initialization(self, oauth_config, mock_auth_state):
        client = SOARAssetOAuthClient(oauth_config, mock_auth_state)
        assert client.config == oauth_config

    def test_client_with_custom_http_client(self, oauth_config, mock_auth_state):
        custom_http = httpx.Client(timeout=60.0)
        client = SOARAssetOAuthClient(
            oauth_config, mock_auth_state, http_client=custom_http
        )
        assert client._http_client == custom_http
        custom_http.close()

    def test_client_with_custom_timeout(self, oauth_config, mock_auth_state):
        client = SOARAssetOAuthClient(oauth_config, mock_auth_state, timeout=60.0)
        assert client._timeout == 60.0

    def test_client_with_verify_ssl_false(self, oauth_config, mock_auth_state):
        client = SOARAssetOAuthClient(oauth_config, mock_auth_state, verify_ssl=False)
        assert client._verify_ssl is False


class TestLoadAndSaveState:
    def test_load_empty_state(self, oauth_client, mock_auth_state):
        state = oauth_client._load_state()
        assert isinstance(state, OAuthState)
        assert state.token is None
        assert state.session is None

    def test_load_state_with_oauth_none(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update({"other_key": "value"})
        state = oauth_client._load_state()
        assert state.token is None

    def test_load_state_with_oauth_data(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {"access_token": "stored_token"},
                    "client_id": "test_client_id",
                }
            }
        )
        state = oauth_client._load_state()
        assert state.token is not None
        assert state.token.access_token == "stored_token"
        assert state.client_id == "test_client_id"

    def test_save_state(self, oauth_client, mock_auth_state):
        token = OAuthToken(access_token="new_token")
        state = OAuthState(token=token, client_id="test_client_id")
        oauth_client._save_state(state)

        saved = mock_auth_state.get_all()
        assert "oauth" in saved
        assert saved["oauth"]["token"]["access_token"] == "new_token"

    def test_load_state_with_non_dict_oauth(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update({"oauth": "invalid"})
        state = oauth_client._load_state()
        assert state.token is None


class TestGetStoredToken:
    def test_get_stored_token_when_exists(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {"access_token": "stored_token"},
                    "client_id": "test_client_id",
                }
            }
        )
        token = oauth_client.get_stored_token()
        assert token is not None
        assert token.access_token == "stored_token"

    def test_get_stored_token_when_none(self, oauth_client):
        token = oauth_client.get_stored_token()
        assert token is None

    def test_get_stored_token_raises_on_client_id_change(
        self, oauth_client, mock_auth_state
    ):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {"access_token": "stored_token"},
                    "client_id": "different_client_id",
                }
            }
        )
        with pytest.raises(ConfigurationChangedError) as exc_info:
            oauth_client.get_stored_token()
        assert "credentials have changed" in str(exc_info.value)


class TestGetValidToken:
    def test_get_valid_token_returns_non_expired(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "valid_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )
        token = oauth_client.get_valid_token()
        assert token.access_token == "valid_token"

    def test_get_valid_token_raises_when_no_token(self, oauth_client):
        with pytest.raises(AuthorizationRequiredError):
            oauth_client.get_valid_token()

    def test_get_valid_token_raises_when_expired_no_refresh(
        self, oauth_client, mock_auth_state
    ):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "expires_at": time.time() - 100,
                    },
                    "client_id": "test_client_id",
                }
            }
        )
        with pytest.raises(TokenExpiredError) as exc_info:
            oauth_client.get_valid_token()
        assert "no refresh token" in str(exc_info.value)

    def test_get_valid_token_raises_when_expired_auto_refresh_false(
        self, oauth_client, mock_auth_state
    ):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "expires_at": time.time() - 100,
                        "refresh_token": "refresh",
                    },
                    "client_id": "test_client_id",
                }
            }
        )
        with pytest.raises(TokenExpiredError):
            oauth_client.get_valid_token(auto_refresh=False)

    @respx.mock
    def test_get_valid_token_auto_refreshes(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "expires_at": time.time() - 100,
                        "refresh_token": "refresh_token",
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new_token",
                    "expires_in": 3600,
                },
            )
        )

        token = oauth_client.get_valid_token()
        assert token.access_token == "new_token"


class TestRefreshToken:
    @respx.mock
    def test_refresh_token_success(self, oauth_client, mock_auth_state):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "refreshed_token",
                    "expires_in": 3600,
                },
            )
        )

        token = oauth_client.refresh_token("old_refresh_token")
        assert token.access_token == "refreshed_token"
        assert token.refresh_token == "old_refresh_token"

    @respx.mock
    def test_refresh_token_preserves_new_refresh_token(
        self, oauth_client, mock_auth_state
    ):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "refreshed_token",
                    "refresh_token": "new_refresh_token",
                    "expires_in": 3600,
                },
            )
        )

        token = oauth_client.refresh_token("old_refresh_token")
        assert token.refresh_token == "new_refresh_token"

    @respx.mock
    def test_refresh_token_http_error(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_grant", "error_description": "Token expired"},
            )
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("invalid_refresh_token")
        assert "Token expired" in str(exc_info.value)

    @respx.mock
    def test_refresh_token_http_error_non_json_response(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(400, content=b"Bad Request - Invalid token")
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("invalid_refresh_token")
        assert "Bad Request" in str(exc_info.value)

    @respx.mock
    def test_refresh_token_network_error(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("refresh_token")
        assert "request failed" in str(exc_info.value)


class TestClientCredentialsFlow:
    @respx.mock
    def test_fetch_token_with_client_credentials(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "cc_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )

        token = oauth_client.fetch_token_with_client_credentials()
        assert token.access_token == "cc_token"

    @respx.mock
    def test_fetch_token_with_extra_params(self, oauth_client):
        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "cc_token", "expires_in": 3600},
            )
        )

        oauth_client.fetch_token_with_client_credentials(
            extra_params={"resource": "https://api.example.com"}
        )

        request = route.calls.last.request
        assert b"resource=https" in request.content

    @respx.mock
    def test_fetch_token_without_client_secret(self, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        token = client.fetch_token_with_client_credentials()
        assert token.access_token == "token"

    @respx.mock
    def test_fetch_token_http_error(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                401,
                json={"error": "invalid_client"},
            )
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_client_credentials()
        assert "failed" in str(exc_info.value)

    @respx.mock
    def test_fetch_token_network_error(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_client_credentials()
        assert "failed" in str(exc_info.value)


class TestAuthorizationCodeFlow:
    def test_create_authorization_url(self, oauth_client):
        url, session = oauth_client.create_authorization_url("asset-123")

        assert "https://auth.example.com/authorize" in url
        assert "client_id=test_client_id" in url
        assert "response_type=code" in url
        assert "state=" in url
        assert session.asset_id == "asset-123"
        assert session.auth_pending is True

    def test_create_authorization_url_with_pkce(self, oauth_client):
        url, session = oauth_client.create_authorization_url("asset-123", use_pkce=True)

        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert session.code_verifier is not None

    def test_create_authorization_url_without_pkce(self, oauth_client):
        url, session = oauth_client.create_authorization_url(
            "asset-123", use_pkce=False
        )

        assert "code_challenge" not in url
        assert session.code_verifier is None

    def test_create_authorization_url_with_extra_params(self, oauth_client):
        url, _ = oauth_client.create_authorization_url(
            "asset-123",
            extra_params={"prompt": "consent", "login_hint": "user@example.com"},
        )

        assert "prompt=consent" in url
        assert "login_hint=user" in url

    def test_create_authorization_url_no_endpoint_raises(self, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        with pytest.raises(OAuthClientError) as exc_info:
            client.create_authorization_url("asset-123")
        assert "authorization_endpoint is required" in str(exc_info.value)

    def test_create_authorization_url_without_redirect_uri(self, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        url, _ = client.create_authorization_url("asset-123", use_pkce=False)

        assert "redirect_uri" not in url

    def test_create_authorization_url_without_scope(self, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        url, _ = client.create_authorization_url("asset-123", use_pkce=False)

        assert "scope" not in url

    @respx.mock
    def test_fetch_token_with_authorization_code(self, oauth_client, mock_auth_state):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "auth_code_token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )

        token = oauth_client.fetch_token_with_authorization_code("auth_code_123")
        assert token.access_token == "auth_code_token"

    @respx.mock
    def test_fetch_token_with_code_verifier(self, oauth_client):
        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        oauth_client.fetch_token_with_authorization_code(
            "auth_code", code_verifier="verifier_value"
        )

        request = route.calls.last.request
        assert b"code_verifier=verifier_value" in request.content

    @respx.mock
    def test_fetch_token_retrieves_code_verifier_from_session(
        self, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123", use_pkce=True)

        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        oauth_client.fetch_token_with_authorization_code("auth_code")

        request = route.calls.last.request
        assert b"code_verifier=" in request.content

    @respx.mock
    def test_fetch_token_clears_session(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        oauth_client.fetch_token_with_authorization_code("auth_code")

        state = oauth_client._load_state()
        assert state.session is None

    @respx.mock
    def test_fetch_token_without_redirect_uri(self, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        client.fetch_token_with_authorization_code("auth_code")

        request = route.calls.last.request
        assert b"redirect_uri" not in request.content

    @respx.mock
    def test_fetch_token_http_error_auth_code(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_grant", "error_description": "Code expired"},
            )
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_authorization_code("expired_code")
        assert "Code expired" in str(exc_info.value)

    @respx.mock
    def test_fetch_token_network_error_auth_code(self, oauth_client):
        respx.post("https://auth.example.com/token").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_authorization_code("auth_code")
        assert "request failed" in str(exc_info.value)


class TestHandleAuthorizationCallback:
    @respx.mock
    def test_handle_callback_success(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "callback_token", "expires_in": 3600},
            )
        )

        state = oauth_client._load_state()
        callback_state = state.session.state

        token = oauth_client.handle_authorization_callback(
            {"code": "auth_code", "state": callback_state}
        )
        assert token.access_token == "callback_token"

    @respx.mock
    def test_handle_callback_without_state(self, oauth_client, mock_auth_state):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "no_state_token", "expires_in": 3600},
            )
        )

        token = oauth_client.handle_authorization_callback({"code": "auth_code"})
        assert token.access_token == "no_state_token"

    def test_handle_callback_with_error(self, oauth_client):
        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.handle_authorization_callback(
                {
                    "error": "access_denied",
                    "error_description": "User denied access",
                }
            )
        assert "access_denied" in str(exc_info.value)

    def test_handle_callback_missing_code(self, oauth_client):
        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.handle_authorization_callback({"state": "some_state"})
        assert "No authorization code" in str(exc_info.value)

    def test_handle_callback_state_mismatch(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.handle_authorization_callback(
                {"code": "auth_code", "state": "wrong_state"}
            )
        assert "State mismatch" in str(exc_info.value)


class TestSessionManagement:
    def test_get_pending_session_when_exists(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        session = oauth_client.get_pending_session()
        assert session is not None
        assert session.asset_id == "asset-123"
        assert session.auth_pending is True

    def test_get_pending_session_when_none(self, oauth_client):
        session = oauth_client.get_pending_session()
        assert session is None

    def test_get_pending_session_when_not_pending(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "session": {
                        "session_id": "sess-123",
                        "asset_id": "asset-123",
                        "auth_pending": False,
                        "auth_complete": True,
                    }
                }
            }
        )
        session = oauth_client.get_pending_session()
        assert session is None

    def test_complete_session_success(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")
        state = oauth_client._load_state()
        session_id = state.session.session_id

        oauth_client.complete_session(session_id, auth_code="code_123")

        state = oauth_client._load_state()
        assert state.session.auth_pending is False
        assert state.session.auth_complete is True
        assert state.session.auth_code == "code_123"

    def test_complete_session_with_error(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")
        state = oauth_client._load_state()
        session_id = state.session.session_id

        oauth_client.complete_session(
            session_id, error="access_denied", error_description="User denied"
        )

        state = oauth_client._load_state()
        assert state.session.auth_pending is False
        assert state.session.auth_complete is False
        assert state.session.error == "access_denied"

    def test_complete_session_wrong_id_ignored(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        oauth_client.complete_session("wrong_session_id", auth_code="code")

        state = oauth_client._load_state()
        assert state.session.auth_pending is True

    def test_clear_session(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")
        oauth_client.clear_session()

        state = oauth_client._load_state()
        assert state.session is None


class TestExtractErrorDetail:
    def test_extract_error_description(self, oauth_client):
        response = httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Token expired"},
        )
        detail = oauth_client._extract_error_detail(response)
        assert detail == "Token expired"

    def test_extract_error_only(self, oauth_client):
        response = httpx.Response(
            400,
            json={"error": "invalid_grant"},
        )
        detail = oauth_client._extract_error_detail(response)
        assert detail == "invalid_grant"

    def test_extract_from_non_json(self, oauth_client):
        response = httpx.Response(400, content=b"Bad Request")
        detail = oauth_client._extract_error_detail(response)
        assert "Bad Request" in detail

    def test_extract_from_empty_response(self, oauth_client):
        response = httpx.Response(500, content=b"")
        detail = oauth_client._extract_error_detail(response)
        assert "500" in detail

    def test_extract_from_json_non_dict(self, oauth_client):
        response = httpx.Response(400, json="error string")
        detail = oauth_client._extract_error_detail(response)
        assert "error string" in detail

    def test_extract_from_json_list(self, oauth_client):
        response = httpx.Response(400, json=["error1", "error2"])
        detail = oauth_client._extract_error_detail(response)
        assert "error1" in detail

    def test_extract_from_dict_without_error_keys(self, oauth_client):
        response = httpx.Response(400, json={"status": "failed", "code": 123})
        detail = oauth_client._extract_error_detail(response)
        assert "failed" in detail or "123" in detail


class TestSetAuthorizationCode:
    def test_set_authorization_code_with_session(self, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        oauth_client.set_authorization_code("auth_code_abc")

        state = oauth_client._load_state()
        assert state.session.auth_code == "auth_code_abc"
        assert state.session.auth_pending is False
        assert state.session.auth_complete is True

    def test_set_authorization_code_without_session(self, oauth_client):
        oauth_client.set_authorization_code("auth_code_abc")
        state = oauth_client._load_state()
        assert state.session is None


class TestGetAuthorizationCode:
    def test_get_authorization_code_returns_code_when_complete(
        self, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123")
        oauth_client.set_authorization_code("the_code")

        code = oauth_client.get_authorization_code()

        assert code == "the_code"

    def test_get_authorization_code_returns_none_when_not_complete(
        self, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123")

        code = oauth_client.get_authorization_code()

        assert code is None

    def test_get_authorization_code_with_force_reload(
        self, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123")
        oauth_client.set_authorization_code("the_code")

        reload_called = []
        original_get_all = mock_auth_state.get_all

        def tracking_get_all(*, force_reload=False):
            reload_called.append(force_reload)
            return original_get_all(force_reload=force_reload)

        mock_auth_state.get_all = tracking_get_all

        oauth_client.get_authorization_code(force_reload=True)

        assert True in reload_called
