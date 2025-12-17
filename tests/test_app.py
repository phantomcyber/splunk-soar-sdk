import json
from unittest import mock

import httpx
import pytest

from soar_sdk.abstract import SOARClient, SOARClientAuth
from soar_sdk.action_results import ActionOutput
from soar_sdk.actions_manager import ActionsManager
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.crypto import encrypt
from soar_sdk.input_spec import AppConfig, InputSpecification
from soar_sdk.params import Params
from soar_sdk.shims.phantom_common.app_interface.app_interface import SoarRestClient
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse


def test_app_run(example_app):
    with mock.patch("soar_sdk.app_cli_runner.AppCliRunner.run") as run_mock:
        example_app.cli()

    assert run_mock.called


def test_handle(example_app: App, simple_action_input: InputSpecification):
    class TestAsset(BaseAsset):
        client_id: str
        client_secret: str = AssetField(sensitive=True)

    example_app.asset_cls = TestAsset

    simple_action_input.config = AppConfig(
        app_version="1.0.0",
        directory=".",
        main_module="example_connector.py",
        client_id="test_client_id",
        client_secret=encrypt("test_client_secret", simple_action_input.asset_id),
    )

    with mock.patch.object(example_app.actions_manager, "handle") as mock_handle:
        example_app.handle(simple_action_input.model_dump_json())

    mock_handle.assert_called_once()
    # Ensure that the encrypted asset configs get decrypted correctly
    assert example_app._raw_asset_config.get("client_id") == "test_client_id"
    assert example_app._raw_asset_config.get("client_secret") == "test_client_secret"


def test_handle_asset_state(example_app: App, simple_action_input: InputSpecification):
    @example_app.action()
    def set_state(params: Params, asset: BaseAsset) -> ActionOutput:
        asset.auth_state["foo"] = 42
        asset.cache_state["hello"] = "world"
        return ActionOutput()

    @example_app.action()
    def get_state(params: Params, asset: BaseAsset) -> ActionOutput:
        assert asset.auth_state["foo"] == 42
        assert asset.cache_state["hello"] == "world"
        assert asset.ingest_state == {}
        return ActionOutput()

    simple_action_input.action = "set_state"
    simple_action_input.identifier = "set_state"
    _ = example_app.handle(simple_action_input.model_dump_json())
    assert example_app.actions_manager.get_action_results()[-1].status

    simple_action_input.action = "get_state"
    simple_action_input.identifier = "get_state"
    _ = example_app.handle(simple_action_input.model_dump_json())
    assert example_app.actions_manager.get_action_results()[-1].status


def test_decrypted_field_not_present(
    example_app: App, simple_action_input: InputSpecification
):
    class TestAsset(BaseAsset):
        client_id: str
        client_secret: str = AssetField(sensitive=True)

    example_app.asset_cls = TestAsset

    simple_action_input.config = AppConfig(
        app_version="1.0.0",
        directory=".",
        main_module="example_connector.py",
        client_id="test_client_id",
        # client_secret is not provided, so it should not be decrypted
    )

    with mock.patch.object(example_app.actions_manager, "handle") as mock_handle:
        example_app.handle(simple_action_input.model_dump_json())

    mock_handle.assert_called_once()
    # Ensure that the encrypted asset configs get decrypted correctly
    assert example_app._raw_asset_config.get("client_id") == "test_client_id"
    assert "client_secret" not in example_app._raw_asset_config


def test_handle_with_sensitive_field_no_errors(
    example_app: App, simple_action_input: InputSpecification
):
    """Test that blank sensitive asset fields work correctly during action execution without throwing errors."""

    class AssetWithSensitive(BaseAsset):
        username: str = AssetField(description="Username")
        password: str = AssetField(sensitive=True, description="Password")

    example_app.asset_cls = AssetWithSensitive

    @example_app.action()
    def test_action(params: Params, asset: AssetWithSensitive) -> ActionOutput:
        assert asset.username == "test_user"
        assert asset.password == ""

        return ActionOutput(
            message="Action completed successfully with sensitive fields"
        )

    simple_action_input.config = AppConfig(
        app_version="1.0",
        directory=".",
        main_module="example_connector.py",
        username="test_user",
        password="",
    )

    # Call handle - this should not throw any errors
    _ = example_app.handle(simple_action_input.model_dump_json())
    assert example_app.actions_manager.get_action_results()[-1].status
    assert example_app._raw_asset_config.get("password") == ""


def test_get_actions(example_app: App):
    @example_app.action()
    def action_handler(params: Params) -> ActionOutput:
        return ActionOutput()

    actions = example_app.get_actions()
    assert len(actions) == 1
    assert "action_handler" in actions
    assert actions["action_handler"] == action_handler


def test_adapt_action_result_with_empty_list_and_summary():
    class SummaryOutput(ActionOutput):
        count: int

    summary = SummaryOutput(count=5)
    result = App._adapt_action_result(
        [],
        ActionsManager(),
        action_params=Params(),
        message="test",
        summary=summary,
    )

    assert result is True


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

    assert app_with_simple_asset.webhook_meta.model_dump() == {
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


def test_handle_webhook_with_state(app_with_asset_webhook: App, mock_get_any_soar_call):
    @app_with_asset_webhook.webhook("stateful_webhook")
    def stateful_webhook(request: WebhookRequest) -> WebhookResponse:
        request.asset.cache_state["hello"] = "world"
        return WebhookResponse.json_response(dict(request.asset.cache_state))

    response = app_with_asset_webhook.handle_webhook(
        method="GET",
        headers={},
        path_parts=["stateful_webhook"],
        query={},
        body=None,
        asset={"base_url": "https://example.com"},
        soar_rest_client=SoarRestClient(token="test_token", asset_id="1"),
    )
    assert response["status_code"] == 200
    assert json.loads(response["content"]) == {"hello": "world"}
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


def test_get_webhook_url(app_with_asset_webhook: App, respx_mock):
    respx_mock.get(url__regex=r".*rest/system_info.*").mock(
        return_value=httpx.Response(
            200,
            json={"base_url": "https://soar.example.com/"},
        )
    )
    respx_mock.get(url__regex=r".*rest/feature_flag/webhooks.*").mock(
        return_value=httpx.Response(
            200,
            json={"config": {"webhooks_port": 4500}},
        )
    )

    app_with_asset_webhook.soar_client.update_client(
        SOARClientAuth(base_url="https://soar.example.com"),
        asset_id="123",
    )

    with mock.patch.object(
        app_with_asset_webhook.actions_manager,
        "get_config",
        return_value={"directory": "my_test_app_dir"},
    ):
        url = app_with_asset_webhook.get_webhook_url("oauth/callback")

    assert (
        url
        == "https://soar.example.com:4500/webhook/my_test_app_dir/123/oauth/callback"
    )


def test_get_webhook_url_without_directory(app_with_asset_webhook: App, respx_mock):
    respx_mock.get(url__regex=r".*rest/system_info.*").mock(
        return_value=httpx.Response(
            200,
            json={"base_url": "https://soar.example.com"},
        )
    )

    app_with_asset_webhook.soar_client.update_client(
        SOARClientAuth(base_url="https://soar.example.com"),
        asset_id="456",
    )

    with mock.patch.object(
        app_with_asset_webhook.actions_manager,
        "get_config",
        return_value={},
    ):
        url = app_with_asset_webhook.get_webhook_url("callback")

    expected_directory = f"{app_with_asset_webhook.app_meta_info['name']}_{app_with_asset_webhook.app_meta_info['appid']}"
    assert (
        url
        == f"https://soar.example.com:3500/webhook/{expected_directory}/456/callback"
    )


def test_get_webhook_port_fallback_on_non_200(app_with_asset_webhook: App):
    app_with_asset_webhook.soar_client.update_client(
        SOARClientAuth(base_url="https://soar.example.com"),
        asset_id="123",
    )

    mock_response = mock.MagicMock()
    mock_response.status_code = 404

    with mock.patch.object(
        app_with_asset_webhook.soar_client, "get", return_value=mock_response
    ):
        port = app_with_asset_webhook._get_webhook_port()

    assert port == 3500


def test_get_webhook_port_fallback_on_missing_port(app_with_asset_webhook: App):
    app_with_asset_webhook.soar_client.update_client(
        SOARClientAuth(base_url="https://soar.example.com"),
        asset_id="123",
    )

    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"config": {}}

    with mock.patch.object(
        app_with_asset_webhook.soar_client, "get", return_value=mock_response
    ):
        port = app_with_asset_webhook._get_webhook_port()

    assert port == 3500


def test_get_webhook_port_fallback_on_exception(app_with_asset_webhook: App):
    app_with_asset_webhook.soar_client.update_client(
        SOARClientAuth(base_url="https://soar.example.com"),
        asset_id="123",
    )

    with mock.patch.object(
        app_with_asset_webhook.soar_client,
        "get",
        side_effect=Exception("Network error"),
    ):
        port = app_with_asset_webhook._get_webhook_port()

    assert port == 3500
