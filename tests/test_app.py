from unittest import mock

from soar_sdk.action_results import ActionOutput
from soar_sdk.app import App
from soar_sdk.crypto import encrypt
from soar_sdk.input_spec import InputSpecification
from soar_sdk.params import Params
import pytest

from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse
from soar_sdk.shims.phantom_common.app_interface.app_interface import SoarRestClient
from soar_sdk.abstract import SOARClientAuth, SOARClient
from soar_sdk.asset import BaseAsset, AssetField


def test_app_run(example_app):
    with mock.patch("soar_sdk.app_cli_runner.AppCliRunner.run") as run_mock:
        example_app.cli()

    assert run_mock.called


def test_handle(example_app: App, simple_action_input: InputSpecification):
    class TestAsset(BaseAsset):
        client_id: str
        client_secret: str = AssetField(sensitive=True)

    example_app.asset_cls = TestAsset

    simple_action_input.config = {
        "app_version": "1.0.0",
        "directory": ".",
        "main_module": "example_connector.py",
        "client_id": "test_client_id",
        "client_secret": encrypt("test_client_secret", simple_action_input.asset_id),
    }

    with mock.patch.object(example_app.actions_manager, "handle") as mock_handle:
        example_app.handle(simple_action_input.json())

    mock_handle.assert_called_once()
    # Ensure that the encrypted asset configs get decrypted correctly
    assert example_app._raw_asset_config.get("client_id") == "test_client_id"
    assert example_app._raw_asset_config.get("client_secret") == "test_client_secret"


def test_decrypted_field_not_present(
    example_app: App, simple_action_input: InputSpecification
):
    class TestAsset(BaseAsset):
        client_id: str
        client_secret: str = AssetField(sensitive=True)

    example_app.asset_cls = TestAsset

    simple_action_input.config = {
        "app_version": "1.0.0",
        "directory": ".",
        "main_module": "example_connector.py",
        "client_id": "test_client_id",
        # client_secret is not provided, so it should not be decrypted
    }

    with mock.patch.object(example_app.actions_manager, "handle") as mock_handle:
        example_app.handle(simple_action_input.json())

    mock_handle.assert_called_once()
    # Ensure that the encrypted asset configs get decrypted correctly
    assert example_app._raw_asset_config.get("client_id") == "test_client_id"
    assert "client_secret" not in example_app._raw_asset_config


def test_get_actions(example_app: App):
    @example_app.action()
    def action_handler(params: Params) -> ActionOutput:
        return ActionOutput()

    actions = example_app.get_actions()
    assert len(actions) == 1
    assert "action_handler" in actions
    assert actions["action_handler"] == action_handler


def test_app_asset(app_with_simple_asset: App):
    """asset is a property which lazily parses the raw config on first access.
    Assert that it is not built until accessed, and it is built exactly once"""

    app_with_simple_asset._raw_asset_config = {"base_url": "https://example.com"}

    assert not hasattr(app_with_simple_asset, "_asset")
    asset = app_with_simple_asset.asset
    assert asset.base_url == "https://example.com"
    assert hasattr(app_with_simple_asset, "_asset")
    assert app_with_simple_asset.asset is asset


def test_appid_not_uuid():
    with pytest.raises(ValueError, match="Appid is not a valid uuid: invalid"):
        App(
            name="example_app",
            appid="invalid",
            app_type="sandbox",
            product_vendor="Splunk Inc.",
            logo="logo.svg",
            logo_dark="logo_dark.svg",
            product_name="Example App",
            publisher="Splunk Inc.",
        )

    with pytest.raises(
        ValueError,
        match="Appid is not a valid uuid: 00000000000000000000000000000000",
    ):
        App(
            name="example_app",
            appid="00000000000000000000000000000000",
            app_type="sandbox",
            product_vendor="Splunk Inc.",
            logo="logo.svg",
            logo_dark="logo_dark.svg",
            product_name="Example App",
            publisher="Splunk Inc.",
        )


def test_enable_webhooks(app_with_simple_asset: App):
    app_with_simple_asset.enable_webhooks(
        default_allowed_headers=["Authorization", "X-Forwarded-For"],
        default_requires_auth=False,
        default_ip_allowlist=["10.0.0.0/24"],
    )

    assert app_with_simple_asset.webhook_meta.dict() == {
        "handler": None,
        "requires_auth": False,
        "allowed_headers": ["Authorization", "X-Forwarded-For"],
        "ip_allowlist": ["10.0.0.0/24"],
        "routes": [],
    }


def test_register_webhook_without_enabling_webhooks_raises(app_with_simple_asset: App):
    with pytest.raises(
        RuntimeError,
        match="Webhooks are not enabled for this app",
    ):

        @app_with_simple_asset.webhook("example_webhook")
        def webhook_handler(request: WebhookRequest) -> WebhookResponse:
            return WebhookResponse.text_response("Hello, world!")


def test_handle_webhook(app_with_asset_webhook: App, mock_get_any_soar_call):
    response = app_with_asset_webhook.handle_webhook(
        method="GET",
        headers={},
        path_parts=["test_webhook"],
        query={},
        body=None,
        asset={"base_url": "https://example.com"},
        soar_rest_client=SoarRestClient(token="test_token", asset_id=1),
    )
    assert response["status_code"] == 200
    assert response["content"] == "Webhook received!"
    assert mock_get_any_soar_call.call_count == 1


def test_handle_webhook_normalizes_querystring(
    app_with_asset_webhook: App, mock_get_any_soar_call
):
    @app_with_asset_webhook.webhook("test_webhook_with_query")
    def webhook_handler(request: WebhookRequest) -> WebhookResponse:
        assert request.query == {
            "string_param": ["value"],
            "list_param": ["value1", "value2"],
            "empty_param": [""],
        }
        return WebhookResponse.text_response("Webhook received!")

    response = app_with_asset_webhook.handle_webhook(
        method="GET",
        headers={},
        path_parts=["test_webhook_with_query"],
        query={
            "string_param": "value",
            "list_param": ["value1", "value2"],
            "empty_param": None,
        },
        body=None,
        asset={"base_url": "https://example.com"},
        soar_rest_client=SoarRestClient(token="test_token", asset_id=1),
    )
    assert response["status_code"] == 200
    assert response["content"] == "Webhook received!"
    assert mock_get_any_soar_call.call_count == 1


def test_handle_webhook_without_enabling_webhooks_raises(
    app_with_simple_asset: App,
):
    with pytest.raises(
        RuntimeError,
        match="Webhooks are not enabled for this app",
    ):
        app_with_simple_asset.handle_webhook(
            method="GET",
            headers={},
            path_parts=["example_webhook"],
            query={},
            body=None,
            asset={"base_url": "https://example.com"},
            soar_rest_client=SoarRestClient(token="test_token", asset_id=1),
        )


def test_handle_webhook_invalid_return_type_raises(
    app_with_asset_webhook: App, mock_get_any_soar_call
):
    @app_with_asset_webhook.webhook("example_webhook")
    def webhook_handler(request: WebhookRequest) -> str:
        return "This is not a valid response type"

    with pytest.raises(
        TypeError,
        match="must return a WebhookResponse",
    ):
        app_with_asset_webhook.handle_webhook(
            method="GET",
            headers={},
            path_parts=["example_webhook"],
            query={},
            body=None,
            asset={"base_url": "https://example.com"},
            soar_rest_client=SoarRestClient(token="test_token", asset_id=1),
        )


def test_handle_webhook_soar_client(
    app_with_asset_webhook: App, mock_get_any_soar_call, mock_delete_any_soar_call
):
    @app_with_asset_webhook.webhook("test_webhook_with_query")
    def webhook_handler(request: WebhookRequest, soar: SOARClient) -> WebhookResponse:
        assert request.query == {
            "string_param": ["value"],
            "list_param": ["value1", "value2"],
            "empty_param": [""],
        }
        soar.get("rest/version")
        soar.delete("rest/containers/1/artifacts/2")
        return WebhookResponse.text_response("Webhook received!")

    response = app_with_asset_webhook.handle_webhook(
        method="GET",
        headers={},
        path_parts=["test_webhook_with_query"],
        query={
            "string_param": "value",
            "list_param": ["value1", "value2"],
            "empty_param": None,
        },
        body=None,
        asset={"base_url": "https://example.com"},
        soar_rest_client=SoarRestClient(token="test_token", asset_id=1),
    )
    assert mock_get_any_soar_call.call_count == 2
    assert mock_delete_any_soar_call.call_count == 1
    assert response["status_code"] == 200
    assert response["content"] == "Webhook received!"


def test_create_soar_client_auth_object(auth_action_input):
    result = App.create_soar_client_auth_object(auth_action_input)
    assert isinstance(result, SOARClientAuth)
    assert result.username == "soar_local_admin"
    assert result.password == "password"


def test_create_soar_client_auth_token_object(auth_token_input):
    result = App.create_soar_client_auth_object(auth_token_input)
    assert isinstance(result, SOARClientAuth)
    assert result.base_url == "https://localhost:9999/"
    assert result.user_session_token == "example_token"
