import time
from unittest.mock import patch

import httpx
import pytest
import respx

from soar_sdk.auth.client import AuthorizationRequiredError, OAuthClientError
from soar_sdk.auth.flows import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
)


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


class TestClientCredentialsFlow:
    @pytest.fixture
    def cc_flow(self, mock_auth_state):
        return ClientCredentialsFlow(
            mock_auth_state,
            client_id="test_client",
            client_secret="test_secret",
            token_endpoint="https://auth.example.com/token",
            scope=["read", "write"],
        )

    @respx.mock
    def test_authenticate_success(self, cc_flow):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "cc_access_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )

        token = cc_flow.authenticate()

        assert token.access_token == "cc_access_token"
        assert token.expires_in == 3600

    @respx.mock
    def test_authenticate_with_extra_params(self, mock_auth_state):
        flow = ClientCredentialsFlow(
            mock_auth_state,
            client_id="test_client",
            client_secret="test_secret",
            token_endpoint="https://auth.example.com/token",
            extra_params={"resource": "https://api.example.com"},
        )

        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        flow.authenticate()

        request = route.calls.last.request
        assert b"resource=" in request.content

    @respx.mock
    def test_get_token_returns_valid_stored_token(self, cc_flow, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "stored_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client",
                }
            }
        )

        token = cc_flow.get_token()
        assert token.access_token == "stored_token"

    @respx.mock
    def test_get_token_fetches_new_when_expired(self, cc_flow, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "expires_at": time.time() - 100,
                    },
                    "client_id": "test_client",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new_token", "expires_in": 3600},
            )
        )

        token = cc_flow.get_token()
        assert token.access_token == "new_token"

    @respx.mock
    def test_get_token_fetches_new_when_none(self, cc_flow):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "fresh_token", "expires_in": 3600},
            )
        )

        token = cc_flow.get_token()
        assert token.access_token == "fresh_token"


class TestAuthorizationCodeFlow:
    @pytest.fixture
    def auth_code_flow(self, mock_auth_state):
        return AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            client_secret="test_secret",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            scope=["openid", "profile"],
        )

    def test_get_authorization_url(self, auth_code_flow):
        url = auth_code_flow.get_authorization_url()

        assert "https://auth.example.com/authorize" in url
        assert "client_id=test_client" in url
        assert "redirect_uri=" in url
        assert "scope=" in url

    def test_get_authorization_url_with_pkce(self, mock_auth_state):
        flow = AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            use_pkce=True,
        )

        url = flow.get_authorization_url()

        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_get_authorization_url_without_pkce(self, mock_auth_state):
        flow = AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            use_pkce=False,
        )

        url = flow.get_authorization_url()

        assert "code_challenge" not in url

    def test_get_authorization_url_with_extra_params(self, mock_auth_state):
        flow = AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            extra_auth_params={"prompt": "consent"},
        )

        url = flow.get_authorization_url()

        assert "prompt=consent" in url

    @respx.mock
    def test_exchange_code_for_token(self, auth_code_flow):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "exchanged_token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )

        token = auth_code_flow.exchange_code_for_token("auth_code_value")

        assert token.access_token == "exchanged_token"
        assert token.refresh_token == "refresh"

    @respx.mock
    def test_exchange_code_with_extra_token_params(self, mock_auth_state):
        flow = AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            extra_token_params={"resource": "https://api.example.com"},
        )

        route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        flow.exchange_code_for_token("auth_code")

        request = route.calls.last.request
        assert b"resource=" in request.content

    def test_authenticate_raises_authorization_required(self, auth_code_flow):
        with pytest.raises(AuthorizationRequiredError) as exc_info:
            auth_code_flow.authenticate()

        assert "authorization required" in str(exc_info.value).lower()
        assert "https://auth.example.com/authorize" in str(exc_info.value)

    @respx.mock
    def test_get_token_returns_valid_token(self, auth_code_flow, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "stored_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client",
                }
            }
        )

        token = auth_code_flow.get_token()
        assert token.access_token == "stored_token"

    @respx.mock
    def test_get_token_auto_refreshes(self, auth_code_flow, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "refresh_token": "refresh_token",
                        "expires_at": time.time() - 100,
                    },
                    "client_id": "test_client",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "refreshed_token", "expires_in": 3600},
            )
        )

        token = auth_code_flow.get_token()
        assert token.access_token == "refreshed_token"

    def test_client_property(self, auth_code_flow):
        client = auth_code_flow.client
        assert client is not None
        assert client.config.client_id == "test_client"

    @respx.mock
    def test_wait_for_authorization_success(self, auth_code_flow, mock_auth_state):
        auth_code_flow.get_authorization_url()

        state_data = mock_auth_state.get_all()
        session = state_data["oauth"]["session"]
        session["auth_pending"] = False
        session["auth_complete"] = True
        session["auth_code"] = "received_code"

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "waited_token", "expires_in": 3600},
            )
        )

        with patch("time.sleep"):
            token = auth_code_flow.wait_for_authorization()

        assert token.access_token == "waited_token"

    def test_wait_for_authorization_timeout(self, mock_auth_state):
        flow = AuthorizationCodeFlow(
            mock_auth_state,
            asset_id="asset-123",
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            poll_timeout=1,
            poll_interval=1,
        )

        flow.get_authorization_url()

        with patch("time.sleep"), patch("time.time") as mock_time:
            mock_time.side_effect = [0, 0.5, 2]
            with pytest.raises(OAuthClientError) as exc_info:
                flow.wait_for_authorization()

        assert "timed out" in str(exc_info.value)

    @respx.mock
    def test_wait_for_authorization_with_progress_callback(
        self, auth_code_flow, mock_auth_state
    ):
        auth_code_flow.get_authorization_url()

        progress_calls = []

        def on_progress(iteration):
            progress_calls.append(iteration)
            state_data = mock_auth_state.get_all()
            session = state_data["oauth"]["session"]
            session["auth_pending"] = False
            session["auth_complete"] = True
            session["auth_code"] = "code"

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        with patch("time.sleep"):
            auth_code_flow.wait_for_authorization(on_progress=on_progress)

        assert len(progress_calls) >= 1
        assert 1 in progress_calls

    def test_set_authorization_code(self, auth_code_flow, mock_auth_state):
        auth_code_flow.get_authorization_url()

        auth_code_flow.set_authorization_code("webhook_code")

        state_data = mock_auth_state.get_all()
        session = state_data["oauth"]["session"]
        assert session["auth_code"] == "webhook_code"
        assert session["auth_complete"] is True
