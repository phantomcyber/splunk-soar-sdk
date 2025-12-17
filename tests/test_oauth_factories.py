import httpx
import pytest

from soar_sdk.auth.factories import (
    create_oauth_auth,
    create_oauth_callback_handler,
    create_oauth_client,
)
from soar_sdk.auth.httpx_auth import OAuthBearerAuth


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
def mock_asset(mock_auth_state):
    class MockAsset:
        def __init__(self):
            self.client_id = "test_client_id"
            self.client_secret = "test_client_secret"
            self.token_endpoint = "https://auth.example.com/token"
            self.auth_state = mock_auth_state

    return MockAsset()


class TestCreateOAuthAuth:
    def test_creates_oauth_auth_from_asset(self, mock_asset):
        auth = create_oauth_auth(mock_asset)
        assert isinstance(auth, OAuthBearerAuth)

    def test_uses_explicit_client_id(self, mock_asset):
        auth = create_oauth_auth(mock_asset, client_id="override_client_id")
        assert auth._oauth_client._config.client_id == "override_client_id"

    def test_uses_explicit_client_secret(self, mock_asset):
        auth = create_oauth_auth(mock_asset, client_secret="override_secret")
        assert auth._oauth_client._config.client_secret == "override_secret"

    def test_uses_explicit_token_endpoint(self, mock_asset):
        auth = create_oauth_auth(
            mock_asset, token_endpoint="https://custom.example.com/token"
        )
        assert (
            auth._oauth_client._config.token_endpoint
            == "https://custom.example.com/token"
        )

    def test_uses_explicit_scope(self, mock_asset):
        auth = create_oauth_auth(mock_asset, scope=["read", "write"])
        assert auth._oauth_client._config.scope == ["read", "write"]

    def test_auto_refresh_default_true(self, mock_asset):
        auth = create_oauth_auth(mock_asset)
        assert auth._auto_refresh is True

    def test_auto_refresh_can_be_disabled(self, mock_asset):
        auth = create_oauth_auth(mock_asset, auto_refresh=False)
        assert auth._auto_refresh is False

    def test_raises_when_no_client_id(self, mock_auth_state):
        class AssetWithoutClientId:
            auth_state = mock_auth_state
            token_endpoint = "https://auth.example.com/token"

        with pytest.raises(ValueError, match="client_id must be provided"):
            create_oauth_auth(AssetWithoutClientId())

    def test_raises_when_no_token_endpoint(self, mock_auth_state):
        class AssetWithoutTokenEndpoint:
            auth_state = mock_auth_state
            client_id = "test_client_id"

        with pytest.raises(ValueError, match="token_endpoint must be provided"):
            create_oauth_auth(AssetWithoutTokenEndpoint())

    def test_uses_token_url_fallback(self, mock_auth_state):
        class AssetWithTokenUrl:
            auth_state = mock_auth_state
            client_id = "test_client_id"
            client_secret = "test_secret"
            token_url = "https://auth.example.com/oauth/token"

        auth = create_oauth_auth(AssetWithTokenUrl())
        assert (
            auth._oauth_client._config.token_endpoint
            == "https://auth.example.com/oauth/token"
        )

    def test_infers_scope_from_string(self, mock_auth_state):
        class AssetWithStringScope:
            auth_state = mock_auth_state
            client_id = "test_client_id"
            client_secret = "test_secret"
            token_endpoint = "https://auth.example.com/token"
            scope = "read write admin"

        auth = create_oauth_auth(AssetWithStringScope())
        assert auth._oauth_client._config.scope == ["read", "write", "admin"]

    def test_infers_scope_from_list(self, mock_auth_state):
        class AssetWithListScope:
            def __init__(self):
                self.auth_state = mock_auth_state
                self.client_id = "test_client_id"
                self.client_secret = "test_secret"
                self.token_endpoint = "https://auth.example.com/token"
                self.scope = ["read", "write"]

        auth = create_oauth_auth(AssetWithListScope())
        assert auth._oauth_client._config.scope == ["read", "write"]

    def test_empty_string_scope_results_in_none(self, mock_auth_state):
        class AssetWithEmptyScope:
            auth_state = mock_auth_state
            client_id = "test_client_id"
            client_secret = "test_secret"
            token_endpoint = "https://auth.example.com/token"
            scope = ""

        auth = create_oauth_auth(AssetWithEmptyScope())
        assert auth._oauth_client._config.scope is None

    def test_explicit_scope_overrides_asset_scope(self, mock_auth_state):
        class AssetWithScope:
            auth_state = mock_auth_state
            client_id = "test_client_id"
            client_secret = "test_secret"
            token_endpoint = "https://auth.example.com/token"
            scope = "asset_scope"

        auth = create_oauth_auth(AssetWithScope(), scope=["explicit"])
        assert auth._oauth_client._config.scope == ["explicit"]


class TestCreateOAuthClient:
    def test_creates_httpx_client(self, mock_asset):
        with create_oauth_client(mock_asset) as client:
            assert isinstance(client, httpx.Client)

    def test_client_has_oauth_auth(self, mock_asset):
        with create_oauth_client(mock_asset) as client:
            assert isinstance(client._auth, OAuthBearerAuth)

    def test_uses_default_timeout(self, mock_asset):
        with create_oauth_client(mock_asset) as client:
            assert client.timeout.connect == 30.0

    def test_uses_custom_timeout(self, mock_asset):
        with create_oauth_client(mock_asset, timeout=60.0) as client:
            assert client.timeout.connect == 60.0

    def test_passes_httpx_kwargs(self, mock_asset):
        with create_oauth_client(mock_asset, follow_redirects=True) as client:
            assert client.follow_redirects is True

    def test_passes_oauth_params_to_auth(self, mock_asset):
        with create_oauth_client(
            mock_asset, scope=["custom_scope"], auto_refresh=False
        ) as client:
            assert client._auth._oauth_client._config.scope == ["custom_scope"]
            assert client._auth._auto_refresh is False


class TestCreateOAuthCallbackHandler:
    def test_creates_callback_handler(self, mock_asset):
        def get_oauth_client(asset):
            from soar_sdk.auth.client import SOARAssetOAuthClient
            from soar_sdk.auth.models import OAuthConfig

            config = OAuthConfig(
                client_id=asset.client_id,
                client_secret=asset.client_secret,
                token_endpoint=asset.token_endpoint,
            )
            return SOARAssetOAuthClient(config, asset.auth_state)

        handler = create_oauth_callback_handler(get_oauth_client)
        assert callable(handler)

    def test_handler_returns_error_on_oauth_error(self, mock_asset):
        def get_oauth_client(asset):
            from soar_sdk.auth.client import SOARAssetOAuthClient
            from soar_sdk.auth.models import OAuthConfig

            config = OAuthConfig(
                client_id=asset.client_id,
                client_secret=asset.client_secret,
                token_endpoint=asset.token_endpoint,
            )
            return SOARAssetOAuthClient(config, asset.auth_state)

        handler = create_oauth_callback_handler(get_oauth_client)

        class MockRequest:
            def __init__(self):
                self.asset = mock_asset
                self.query = {
                    "error": ["access_denied"],
                    "error_description": ["User denied"],
                }

        response = handler(MockRequest())
        assert response.status_code == 400
        assert "Authorization failed" in response.content

    def test_handler_returns_error_on_missing_code(self, mock_asset):
        def get_oauth_client(asset):
            from soar_sdk.auth.client import SOARAssetOAuthClient
            from soar_sdk.auth.models import OAuthConfig

            config = OAuthConfig(
                client_id=asset.client_id,
                client_secret=asset.client_secret,
                token_endpoint=asset.token_endpoint,
            )
            return SOARAssetOAuthClient(config, asset.auth_state)

        handler = create_oauth_callback_handler(get_oauth_client)

        class MockRequest:
            def __init__(self):
                self.asset = mock_asset
                self.query = {}

        response = handler(MockRequest())
        assert response.status_code == 400
        assert "Missing authorization code" in response.content

    def test_handler_stores_auth_code_on_success(self, mock_asset):
        def get_oauth_client(asset):
            from soar_sdk.auth.client import SOARAssetOAuthClient
            from soar_sdk.auth.models import OAuthConfig

            config = OAuthConfig(
                client_id=asset.client_id,
                client_secret=asset.client_secret,
                token_endpoint=asset.token_endpoint,
            )
            return SOARAssetOAuthClient(config, asset.auth_state)

        handler = create_oauth_callback_handler(get_oauth_client)

        class MockRequest:
            def __init__(self):
                self.asset = mock_asset
                self.query = {"code": ["auth_code_123"]}

        response = handler(MockRequest())
        assert response.status_code == 200
        assert "Authorization successful" in response.content

    def test_handler_uses_custom_success_message(self, mock_asset):
        def get_oauth_client(asset):
            from soar_sdk.auth.client import SOARAssetOAuthClient
            from soar_sdk.auth.models import OAuthConfig

            config = OAuthConfig(
                client_id=asset.client_id,
                client_secret=asset.client_secret,
                token_endpoint=asset.token_endpoint,
            )
            return SOARAssetOAuthClient(config, asset.auth_state)

        handler = create_oauth_callback_handler(
            get_oauth_client, success_message="Custom success!"
        )

        class MockRequest:
            def __init__(self):
                self.asset = mock_asset
                self.query = {"code": ["auth_code_123"]}

        response = handler(MockRequest())
        assert "Custom success!" in response.content
