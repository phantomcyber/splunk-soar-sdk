#!/usr/bin/env python
from io import BytesIO
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

logger = getLogger()


class Asset(BaseAsset):
    base_url: str
    api_key: str = AssetField(sensitive=True, description="API key for authentication")
    key_header: str = AssetField(
        default="Authorization",
        value_list=["Authorization", "X-API-Key"],
        description="Header for API key authentication",
    )


app = App(
    asset_cls=Asset,
    name="example_app",
    appid="9b388c08-67de-4ca4-817f-26f8fb7cbf55",
    app_type="sandbox",
    product_vendor="Splunk Inc.",
    logo="logo.svg",
    logo_dark="logo_dark.svg",
    product_name="Example App",
    publisher="Splunk Inc.",
    min_phantom_version="6.2.2.134",
).enable_webhooks()


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    logger.info(f"testing connectivity against {asset.base_url}")


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(action_type="test", verbose="Reverses a string.")
def reverse_string(
    param: ReverseStringParams, client: SOARClient
) -> ReverseStringOutput:
    logger.debug("params: %s", param)
    reversed_string = param.input_string[::-1]
    logger.debug("reversed_string %s", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


@app.webhook("test_webhook")
def test_webhook(request: WebhookRequest[Asset]) -> WebhookResponse:
    logger.debug("Webhook request: %s", request)
    response = WebhookResponse.text_response(
        content="Webhook received",
        status_code=200,
        extra_headers={"X-Custom-Header": "CustomValue"},
    )
    return response


@app.webhook("test_webhook/<asset_id>", allowed_methods=["GET", "POST", "DELETE"])
def test_webhook_with_asset_id(
    request: WebhookRequest[Asset], asset_id: str
) -> WebhookResponse:
    logger.debug("Webhook with asset ID request: %s", request)
    response = WebhookResponse.text_response(
        content=f"Webhook received with asset ID: {asset_id}",
        status_code=200,
        extra_headers={"X-Custom-Header": "CustomValue"},
    )
    return response


@app.webhook("test_webhook_file")
def test_webhook_file(request: WebhookRequest[Asset]) -> WebhookResponse:
    logger.debug("Webhook file request: %s", request)

    return WebhookResponse.file_response(
        fd=BytesIO(b"Hello, this is a test file content."),
        filename="test_file.txt",
        status_code=200,
        extra_headers={"Content-Disposition": 'attachment; filename="test_file.txt"'},
    )


if __name__ == "__main__":
    app.cli()
