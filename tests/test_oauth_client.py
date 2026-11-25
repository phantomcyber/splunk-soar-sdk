import time
import traceback
from base64 import b64decode
from urllib.parse import parse_qs

import httpx2
import pytest
from respx import MockResponse

from soar_sdk.auth import OAuthBearerAuth, OAuthGrantType
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


class TestPasswordGrant:
    token_endpoint = "https://auth.example.com/token"
    client_id = "test client:+é"
    client_secret = "test secret:+雪"
    username = "test user+é@example.com"
    password = "test password+雪&="

    @pytest.fixture
    def make_client(self, mock_auth_state):
        def make_client(*, http_client=None, verify_ssl=True, **overrides):
            config = OAuthConfig(
                **{
                    "grant_type": OAuthGrantType.PASSWORD,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "token_endpoint": self.token_endpoint,
                    **overrides,
                }
            )
            return SOARAssetOAuthClient(
                config, mock_auth_state, http_client=http_client, verify_ssl=verify_ssl
            )

        return make_client

    def enroll(self, client):
        return client.fetch_token_with_password(
            username=self.username, password=self.password
        )

    @pytest.mark.parametrize(
        "auth_override, in_body",
        [
            ({}, {}),
            ({"token_endpoint_auth_method": "client_secret_basic"}, {}),
            (
                {"token_endpoint_auth_method": "client_secret_post"},
                {"client_id": [client_id], "client_secret": [client_secret]},
            ),
            (
                {"token_endpoint_auth_method": "none", "client_secret": None},
                {"client_id": [client_id]},
            ),
        ],
    )
    def test_exchange_and_refresh_authentication(
        self, httpx2_mock, make_client, auth_override, in_body
    ):
        client = make_client(scope=["read", "write"], **auth_override)
        endpoint = httpx2_mock.post(self.token_endpoint).mock(
            side_effect=[
                MockResponse(
                    200, json={"access_token": "initial", "refresh_token": "saved"}
                ),
                MockResponse(200, json={"access_token": "renewed"}),
                MockResponse(
                    200,
                    json={"access_token": "rotated", "refresh_token": "replacement"},
                ),
            ]
        )

        assert self.enroll(client).access_token == "initial"
        assert client.refresh_token("saved").refresh_token == "saved"
        assert client.refresh_token("saved").refresh_token == "replacement"
        assert client.get_valid_token().access_token == "rotated"
        assert client.get_valid_token().refresh_token == "replacement"

        exchange, refresh, _ = (call.request for call in endpoint.calls)
        assert parse_qs(exchange.content.decode()) == {
            "grant_type": ["password"],
            "username": [self.username],
            "password": [self.password],
            "scope": ["read write"],
            **in_body,
        }
        assert parse_qs(refresh.content.decode()) == {
            "grant_type": ["refresh_token"],
            "refresh_token": ["saved"],
            **in_body,
        }
        for request in (exchange, refresh):
            assert (
                request.headers["content-type"] == "application/x-www-form-urlencoded"
            )
            assert not request.url.query
            if in_body:
                assert "Authorization" not in request.headers
            else:
                scheme, encoded = request.headers["Authorization"].split()
                assert scheme == "Basic"
                assert (
                    b64decode(encoded)
                    == b"test+client%3A%2B%C3%A9:test+secret%3A%2B%E9%9B%AA"
                )

    @pytest.mark.parametrize("expires_in", [0, 3600])
    def test_bearer_auth_refreshes_after_enrollment(
        self, httpx2_mock, make_client, expires_in
    ):
        endpoint = httpx2_mock.post(self.token_endpoint).mock(
            side_effect=[
                MockResponse(
                    200,
                    json={
                        "access_token": "initial",
                        "refresh_token": "saved",
                        "expires_in": expires_in,
                    },
                ),
                MockResponse(200, json={"access_token": "renewed"}),
            ]
        )
        api = httpx2_mock.get("https://api.example.com/resource")
        if expires_in:
            api.mock(side_effect=[MockResponse(401), MockResponse(200)])
        else:
            api.respond(200)

        with pytest.raises(AuthorizationRequiredError):
            make_client().get_valid_token()
        assert not endpoint.called
        self.enroll(make_client())
        with httpx2.Client(auth=OAuthBearerAuth(make_client())) as client:
            assert client.get("https://api.example.com/resource").status_code == 200

        assert api.calls.last.request.headers["Authorization"] == "Bearer renewed"
        assert endpoint.call_count == 2
        assert b"grant_type=refresh_token" in endpoint.calls.last.request.content

    def test_failed_refresh_allows_explicit_reacquisition(
        self, httpx2_mock, make_client
    ):
        endpoint = httpx2_mock.post(self.token_endpoint).mock(
            side_effect=[
                MockResponse(
                    200,
                    json={
                        "access_token": "expired",
                        "refresh_token": "saved",
                        "expires_in": 0,
                    },
                ),
                MockResponse(
                    400, json={"error": "invalid_grant", "error_description": "saved"}
                ),
                MockResponse(200, json={"access_token": "reacquired"}),
            ]
        )
        client = make_client()
        self.enroll(client)
        with pytest.raises(TokenRefreshError, match=r"HTTP 400\)") as exc:
            client.get_valid_token()
        assert "saved" not in str(exc.value)
        assert endpoint.call_count == 2
        assert client.get_stored_token().access_token == "expired"
        assert self.enroll(client).access_token == "reacquired"
        assert client.get_valid_token().refresh_token is None

    def test_state_is_separate_and_contains_only_token_data(
        self, httpx2_mock, make_client, mock_auth_state, oauth_client
    ):
        existing_state = {"token": {"access_token": "other"}}
        mock_auth_state.put_all({"oauth": existing_state})
        httpx2_mock.post(self.token_endpoint).respond(
            200,
            json={
                "access_token": "password-grant-token",
                "echoed_password": self.password,
            },
        )

        client = make_client()
        assert client.get_stored_token() is None
        assert self.enroll(client).model_extra == {}
        assert make_client().get_valid_token().access_token == "password-grant-token"
        assert oauth_client.get_valid_token().access_token == "other"
        assert mock_auth_state.get_all() == {
            "oauth": existing_state,
            "oauth_password": {
                "token": {
                    "access_token": "password-grant-token",
                    "token_type": "Bearer",
                },
                "client_id": self.client_id,
                "token_endpoint": self.token_endpoint,
            },
        }

    @pytest.mark.parametrize(
        "changed",
        [
            {"client_id": "different"},
            {"token_endpoint": "https://other.example.com/token"},
        ],
    )
    def test_cache_binding(self, httpx2_mock, make_client, changed):
        httpx2_mock.post(self.token_endpoint).respond(
            200,
            json={"access_token": "initial", "refresh_token": "saved", "expires_in": 0},
        )
        self.enroll(make_client())
        client = make_client(**changed)
        with pytest.raises(
            ConfigurationChangedError, match="client ID or token endpoint"
        ):
            client.get_valid_token()
        assert client.get_stored_token() is None
        assert len(httpx2_mock.calls) == 1

    @pytest.mark.parametrize(
        "config, message",
        [
            (
                {"grant_type": OAuthGrantType.AUTHORIZATION_CODE},
                "configured explicitly",
            ),
            ({"token_endpoint": "http://auth.example.com/token"}, "verified HTTPS"),
            ({"token_endpoint": "https:/token"}, "verified HTTPS"),
            (
                {"token_endpoint": "https://user:secret@auth.example.com/token"},
                "verified HTTPS",
            ),
            ({"token_endpoint": "https://[invalid]/token"}, "endpoint is invalid"),
            ({"verify_ssl": False}, "verified HTTPS"),
            ({"client_id": ""}, "requires a client ID"),
            ({"client_secret": None}, "requires a client secret"),
            (
                {
                    "client_secret": None,
                    "token_endpoint_auth_method": "client_secret_post",
                },
                "requires a client secret",
            ),
        ],
    )
    def test_rejects_invalid_configuration_before_sending(
        self, httpx2_mock, make_client, config, message
    ):
        with pytest.raises(OAuthClientError, match=message):
            self.enroll(make_client(**config))
        assert not httpx2_mock.calls

    @pytest.mark.parametrize(
        "username,password", [("", "test password"), ("test user", "")]
    )
    def test_requires_resource_owner_credentials(
        self, httpx2_mock, make_client, username, password
    ):
        with pytest.raises(OAuthClientError, match="requires a username and password"):
            make_client().fetch_token_with_password(
                username=username, password=password
            )
        assert not httpx2_mock.calls

    def test_does_not_follow_redirects_or_inherit_client_auth(
        self, httpx2_mock, make_client
    ):
        endpoint = httpx2_mock.post(self.token_endpoint).respond(
            307, headers={"Location": "https://other.example.com/token"}
        )
        with httpx2.Client(
            follow_redirects=True,
            auth=("other-client", "other-secret"),
            headers={"Authorization": "Bearer different"},
        ) as http_client:
            client = make_client(
                http_client=http_client, token_endpoint_auth_method="none"
            )
            with pytest.raises(OAuthClientError, match=r"HTTP 307\)"):
                self.enroll(client)
        assert len(httpx2_mock.calls) == 1
        assert "Authorization" not in endpoint.calls.last.request.headers

    @pytest.mark.parametrize(
        "failure",
        [
            httpx2.ConnectError(password),
            MockResponse(400, json={"error_description": password}),
            MockResponse(200, text=password),
            MockResponse(200, json=[password]),
            MockResponse(200, json={"access_token": "", "scope": password}),
            MockResponse(200, json={"expires_in": password}),
        ],
    )
    def test_failed_exchange_keeps_state_and_sanitizes_error(
        self, httpx2_mock, make_client, mock_auth_state, failure
    ):
        httpx2_mock.post(self.token_endpoint).mock(
            side_effect=[
                MockResponse(200, json={"access_token": "initial"}),
                failure,
            ]
        )
        client = make_client()
        self.enroll(client)
        state_before = mock_auth_state.get_all().copy()

        with pytest.raises(OAuthClientError) as exc:
            self.enroll(client)

        assert self.password not in "".join(traceback.format_exception(exc.value))
        assert mock_auth_state.get_all() == state_before


class TestSOARAssetOAuthClientInit:
    def test_client_initialization(self, oauth_config, mock_auth_state):
        client = SOARAssetOAuthClient(oauth_config, mock_auth_state)
        assert client.config == oauth_config

    def test_client_with_custom_http_client(self, oauth_config, mock_auth_state):
        custom_http = httpx2.Client(timeout=60.0)
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

    def test_get_valid_token_auto_refreshes(
        self, httpx2_mock, oauth_client, mock_auth_state
    ):
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

        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={
                "access_token": "new_token",
                "expires_in": 3600,
            },
        )

        token = oauth_client.get_valid_token()
        assert token.access_token == "new_token"


class TestRefreshToken:
    def test_refresh_token_success(self, httpx2_mock, oauth_client, mock_auth_state):
        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={
                "access_token": "refreshed_token",
                "expires_in": 3600,
            },
        )

        token = oauth_client.refresh_token("old_refresh_token")
        assert token.access_token == "refreshed_token"
        assert token.refresh_token == "old_refresh_token"

    def test_refresh_token_preserves_new_refresh_token(
        self, httpx2_mock, oauth_client, mock_auth_state
    ):
        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={
                "access_token": "refreshed_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600,
            },
        )

        token = oauth_client.refresh_token("old_refresh_token")
        assert token.refresh_token == "new_refresh_token"

    def test_refresh_token_http_error(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").respond(
            400,
            json={"error": "invalid_grant", "error_description": "Token expired"},
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("invalid_refresh_token")
        assert "Token expired" in str(exc_info.value)

    def test_refresh_token_http_error_non_json_response(
        self, httpx2_mock, oauth_client
    ):
        httpx2_mock.post("https://auth.example.com/token").respond(
            400, content=b"Bad Request - Invalid token"
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("invalid_refresh_token")
        assert "Bad Request" in str(exc_info.value)

    def test_refresh_token_network_error(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").mock(
            side_effect=httpx2.ConnectError("Connection failed")
        )

        with pytest.raises(TokenRefreshError) as exc_info:
            oauth_client.refresh_token("refresh_token")
        assert "request failed" in str(exc_info.value)


class TestClientCredentialsFlow:
    def test_fetch_token_with_client_credentials(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={
                "access_token": "cc_token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

        token = oauth_client.fetch_token_with_client_credentials()
        assert token.access_token == "cc_token"

    def test_fetch_token_with_extra_params(self, httpx2_mock, oauth_client):
        route = httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "cc_token", "expires_in": 3600},
        )

        oauth_client.fetch_token_with_client_credentials(
            extra_params={"resource": "https://api.example.com"}
        )

        request = route.calls.last.request
        assert b"resource=https" in request.content

    def test_fetch_token_without_client_secret(self, httpx2_mock, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "token", "expires_in": 3600},
        )

        token = client.fetch_token_with_client_credentials()
        assert token.access_token == "token"

    def test_fetch_token_http_error(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").respond(
            401,
            json={"error": "invalid_client"},
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_client_credentials()
        assert "failed" in str(exc_info.value)

    def test_fetch_token_network_error(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").mock(
            side_effect=httpx2.ConnectError("Connection refused")
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

    def test_fetch_token_with_authorization_code(
        self, httpx2_mock, oauth_client, mock_auth_state
    ):
        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={
                "access_token": "auth_code_token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )

        token = oauth_client.fetch_token_with_authorization_code("auth_code_123")
        assert token.access_token == "auth_code_token"

    def test_fetch_token_with_code_verifier(self, httpx2_mock, oauth_client):
        route = httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "token", "expires_in": 3600},
        )

        oauth_client.fetch_token_with_authorization_code(
            "auth_code", code_verifier="verifier_value"
        )

        request = route.calls.last.request
        assert b"code_verifier=verifier_value" in request.content

    def test_fetch_token_retrieves_code_verifier_from_session(
        self, httpx2_mock, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123", use_pkce=True)

        route = httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "token", "expires_in": 3600},
        )

        oauth_client.fetch_token_with_authorization_code("auth_code")

        request = route.calls.last.request
        assert b"code_verifier=" in request.content

    def test_fetch_token_clears_session(
        self, httpx2_mock, oauth_client, mock_auth_state
    ):
        oauth_client.create_authorization_url("asset-123")

        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "token", "expires_in": 3600},
        )

        oauth_client.fetch_token_with_authorization_code("auth_code")

        state = oauth_client._load_state()
        assert state.session is None

    def test_fetch_token_without_redirect_uri(self, httpx2_mock, mock_auth_state):
        config = OAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
        )
        client = SOARAssetOAuthClient(config, mock_auth_state)

        route = httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "token", "expires_in": 3600},
        )

        client.fetch_token_with_authorization_code("auth_code")

        request = route.calls.last.request
        assert b"redirect_uri" not in request.content

    def test_fetch_token_http_error_auth_code(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").respond(
            400,
            json={"error": "invalid_grant", "error_description": "Code expired"},
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_authorization_code("expired_code")
        assert "Code expired" in str(exc_info.value)

    def test_fetch_token_network_error_auth_code(self, httpx2_mock, oauth_client):
        httpx2_mock.post("https://auth.example.com/token").mock(
            side_effect=httpx2.ConnectError("Connection refused")
        )

        with pytest.raises(OAuthClientError) as exc_info:
            oauth_client.fetch_token_with_authorization_code("auth_code")
        assert "request failed" in str(exc_info.value)


class TestHandleAuthorizationCallback:
    def test_handle_callback_success(self, httpx2_mock, oauth_client, mock_auth_state):
        oauth_client.create_authorization_url("asset-123")

        httpx2_mock.post("https://auth.example.com/token").respond(
            200,
            json={"access_token": "callback_token", "expires_in": 3600},
        )

        state = oauth_client._load_state()
        callback_state = state.session.state

        token = oauth_client.handle_authorization_callback(
            {"code": "auth_code", "state": callback_state}
        )
        assert token.access_token == "callback_token"

    def test_handle_callback_without_state(self, oauth_client):
        with pytest.raises(OAuthClientError, match="Missing state"):
            oauth_client.handle_authorization_callback({"code": "auth_code"})

    def test_handle_callback_without_pending_session(self, oauth_client):
        with pytest.raises(OAuthClientError, match="No pending authorization session"):
            oauth_client.handle_authorization_callback(
                {"code": "auth_code", "state": "some_state"}
            )

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
        response = httpx2.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Token expired"},
        )
        detail = oauth_client._extract_error_detail(response)
        assert detail == "Token expired"

    def test_extract_error_only(self, oauth_client):
        response = httpx2.Response(
            400,
            json={"error": "invalid_grant"},
        )
        detail = oauth_client._extract_error_detail(response)
        assert detail == "invalid_grant"

    def test_extract_from_non_json(self, oauth_client):
        response = httpx2.Response(400, content=b"Bad Request")
        detail = oauth_client._extract_error_detail(response)
        assert "Bad Request" in detail

    def test_extract_from_empty_response(self, oauth_client):
        response = httpx2.Response(500, content=b"")
        detail = oauth_client._extract_error_detail(response)
        assert "500" in detail

    def test_extract_from_json_non_dict(self, oauth_client):
        response = httpx2.Response(400, json="error string")
        detail = oauth_client._extract_error_detail(response)
        assert "error string" in detail

    def test_extract_from_json_list(self, oauth_client):
        response = httpx2.Response(400, json=["error1", "error2"])
        detail = oauth_client._extract_error_detail(response)
        assert "error1" in detail

    def test_extract_from_dict_without_error_keys(self, oauth_client):
        response = httpx2.Response(400, json={"status": "failed", "code": 123})
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
