import time

import httpx
import pytest
import respx

from soar_sdk.oauth.client import (
    SOARAssetOAuthClient,
)
from soar_sdk.oauth.httpx_auth import (
    OAuthBearerAuth,
    OAuthClientCredentialsAuth,
    StaticTokenAuth,
    create_oauth_auth,
)
from soar_sdk.oauth.models import OAuthConfig, OAuthToken


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
        token_endpoint="https://auth.example.com/token",
        scope=["read", "write"],
    )


@pytest.fixture
def oauth_client(oauth_config, mock_auth_state):
    return SOARAssetOAuthClient(oauth_config, mock_auth_state)


class TestStaticTokenAuth:
    def test_auth_with_oauth_token(self):
        token = OAuthToken(access_token="test_token", token_type="Bearer")
        auth = StaticTokenAuth(token)

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer test_token"

    def test_auth_with_string_token(self):
        auth = StaticTokenAuth("string_token")

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer string_token"

    def test_auth_with_custom_token_type(self):
        auth = StaticTokenAuth("api_key", token_type="ApiKey")

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "ApiKey api_key"

    def test_auth_uses_token_type_from_oauth_token(self):
        token = OAuthToken(access_token="test_token", token_type="CustomType")
        auth = StaticTokenAuth(token)

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "CustomType test_token"


class TestOAuthBearerAuth:
    @respx.mock
    def test_auth_fetches_token_when_none(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "fresh_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        auth = OAuthBearerAuth(oauth_client)
        assert auth._token is None

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer fresh_token"
        assert auth._token is not None

    @respx.mock
    def test_auth_injects_bearer_token(self, oauth_client, mock_auth_state):
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

        auth = OAuthBearerAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer valid_token"

    @respx.mock
    def test_auth_uses_existing_valid_token(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "stored_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        auth = OAuthBearerAuth(oauth_client)
        auth._token = OAuthToken(
            access_token="pre_cached_token",
            expires_at=time.time() + 3600,
        )

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert (
            authenticated_request.headers["Authorization"] == "Bearer pre_cached_token"
        )

    @respx.mock
    def test_auth_refreshes_expired_token(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "expired_token",
                        "refresh_token": "refresh_token",
                        "expires_at": time.time() - 100,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "refreshed_token", "expires_in": 3600},
            )
        )

        auth = OAuthBearerAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert (
            authenticated_request.headers["Authorization"] == "Bearer refreshed_token"
        )

    @respx.mock
    def test_auth_refreshes_on_401_response(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "token_that_will_fail",
                        "refresh_token": "refresh_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new_token", "expires_in": 3600},
            )
        )

        auth = OAuthBearerAuth(oauth_client, auto_refresh=True)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)

        first_request = next(flow)
        assert first_request.headers["Authorization"] == "Bearer token_that_will_fail"

        response_401 = httpx.Response(401)
        retry_request = flow.send(response_401)
        assert retry_request.headers["Authorization"] == "Bearer new_token"

    @respx.mock
    def test_auth_no_refresh_when_disabled(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "token",
                        "refresh_token": "refresh_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        auth = OAuthBearerAuth(oauth_client, auto_refresh=False)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)

        next(flow)
        response_401 = httpx.Response(401)

        with pytest.raises(StopIteration):
            flow.send(response_401)

    @respx.mock
    def test_auth_no_refresh_without_refresh_token(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        auth = OAuthBearerAuth(oauth_client, auto_refresh=True)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)

        next(flow)
        response_401 = httpx.Response(401)

        with pytest.raises(StopIteration):
            flow.send(response_401)

    def test_requires_response_body(self, oauth_client):
        auth = OAuthBearerAuth(oauth_client)
        assert auth.requires_response_body is True


class TestOAuthClientCredentialsAuth:
    @respx.mock
    def test_auth_fetches_token_on_first_request(self, oauth_client, mock_auth_state):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "cc_token", "expires_in": 3600},
            )
        )

        auth = OAuthClientCredentialsAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer cc_token"

    @respx.mock
    def test_auth_fetches_when_get_valid_token_raises(
        self, oauth_client, mock_auth_state
    ):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "fetched_token", "expires_in": 3600},
            )
        )

        auth = OAuthClientCredentialsAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer fetched_token"

    @respx.mock
    def test_auth_uses_cached_valid_token(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "cached_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        auth = OAuthClientCredentialsAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer cached_token"

    @respx.mock
    def test_auth_uses_internally_cached_token(self, oauth_client, mock_auth_state):
        auth = OAuthClientCredentialsAuth(oauth_client)
        auth._token = OAuthToken(
            access_token="internally_cached",
            expires_at=time.time() + 3600,
        )

        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert (
            authenticated_request.headers["Authorization"] == "Bearer internally_cached"
        )

    @respx.mock
    def test_auth_fetches_new_token_when_expired(self, oauth_client, mock_auth_state):
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

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new_cc_token", "expires_in": 3600},
            )
        )

        auth = OAuthClientCredentialsAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer new_cc_token"

    @respx.mock
    def test_auth_fetches_new_token_on_401(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "will_fail_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "retry_token", "expires_in": 3600},
            )
        )

        auth = OAuthClientCredentialsAuth(oauth_client)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)

        first_request = next(flow)
        assert first_request.headers["Authorization"] == "Bearer will_fail_token"

        response_401 = httpx.Response(401)
        retry_request = flow.send(response_401)
        assert retry_request.headers["Authorization"] == "Bearer retry_token"

    @respx.mock
    def test_auth_with_custom_leeway(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "soon_expiring_token",
                        "expires_at": time.time() + 30,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new_token", "expires_in": 3600},
            )
        )

        auth = OAuthClientCredentialsAuth(oauth_client, token_leeway=60)
        request = httpx.Request("GET", "https://api.example.com/data")
        flow = auth.auth_flow(request)
        authenticated_request = next(flow)

        assert authenticated_request.headers["Authorization"] == "Bearer new_token"

    def test_requires_response_body(self, oauth_client):
        auth = OAuthClientCredentialsAuth(oauth_client)
        assert auth.requires_response_body is True


class TestCreateOAuthAuth:
    def test_returns_oauth_bearer_auth(self, oauth_client):
        auth = create_oauth_auth(oauth_client)
        assert isinstance(auth, OAuthBearerAuth)

    def test_auto_refresh_true_by_default(self, oauth_client):
        auth = create_oauth_auth(oauth_client)
        assert auth._auto_refresh is True

    def test_auto_refresh_can_be_disabled(self, oauth_client):
        auth = create_oauth_auth(oauth_client, auto_refresh=False)
        assert auth._auto_refresh is False


class TestIntegrationWithHttpxClient:
    @respx.mock
    def test_static_auth_with_httpx_client(self):
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )

        auth = StaticTokenAuth("my_api_token")

        with httpx.Client(auth=auth) as client:
            response = client.get("https://api.example.com/data")

        assert response.status_code == 200
        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer my_api_token"

    @respx.mock
    def test_bearer_auth_with_httpx_client(self, oauth_client, mock_auth_state):
        mock_auth_state._data.update(
            {
                "oauth": {
                    "token": {
                        "access_token": "bearer_token",
                        "expires_at": time.time() + 3600,
                    },
                    "client_id": "test_client_id",
                }
            }
        )

        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )

        auth = OAuthBearerAuth(oauth_client)

        with httpx.Client(auth=auth) as client:
            response = client.get("https://api.example.com/data")

        assert response.status_code == 200
        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer bearer_token"

    @respx.mock
    def test_client_credentials_auth_with_httpx_client(
        self, oauth_client, mock_auth_state
    ):
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "cc_token", "expires_in": 3600},
            )
        )
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )

        auth = OAuthClientCredentialsAuth(oauth_client)

        with httpx.Client(auth=auth) as client:
            response = client.get("https://api.example.com/data")

        assert response.status_code == 200
        api_request = next(
            r for r in respx.calls if "api.example.com" in str(r.request.url)
        )
        assert api_request.request.headers["Authorization"] == "Bearer cc_token"
