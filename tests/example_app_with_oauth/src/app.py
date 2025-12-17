from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.auth import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
    OAuthConfig,
    SOARAssetOAuthClient,
    create_oauth_client,
)
from soar_sdk.logging import getLogger
from soar_sdk.params import Params
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

logger = getLogger()

APP_NAME = "example_app_with_oauth"
APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf56"


class Asset(BaseAsset):
    domain: str = AssetField(
        description="URL of service to authenticate against",
    )
    auth_type: str = AssetField(
        default="credentials",
        value_list=["credentials", "interactive"],
        description="Authentication method",
    )
    client_id: str = AssetField(description="OAuth Client ID")
    client_secret: str = AssetField(
        sensitive=True,
        description="OAuth Client Secret",
    )
    tenant_id: str | None = AssetField(
        default=None,
        description="Service Tenant ID (appended to domain if provided)",
    )
    token_uri: str = AssetField(default="/oauth2/v2.0/token")
    auth_uri: str = AssetField(default="/oauth2/v2.0/authorize")
    scope: str = AssetField(
        default="",
        description="OAuth scope (space-separated if multiple)",
    )

    @property
    def token_url(self) -> str:
        base = self.domain.rstrip("/")
        if self.tenant_id:
            return f"{base}/{self.tenant_id}/{self.token_uri.lstrip('/')}"
        return f"{base}/{self.token_uri.lstrip('/')}"

    @property
    def auth_url(self) -> str:
        base = self.domain.rstrip("/")
        if self.tenant_id:
            return f"{base}/{self.tenant_id}/{self.auth_uri.lstrip('/')}"
        return f"{base}/{self.auth_uri.lstrip('/')}"


app = App(
    asset_cls=Asset,
    name=APP_NAME,
    appid=APP_ID,
    app_type="endpoint",
    product_vendor="Splunk Inc.",
    logo="logo.svg",
    logo_dark="logo_dark.svg",
    product_name="Example OAuth App",
    publisher="Splunk Inc.",
).enable_webhooks(default_requires_auth=False)


def get_scopes(asset: Asset) -> list[str]:
    return asset.scope.split() if asset.scope else []


def get_oauth_client(
    asset: Asset, redirect_uri: str | None = None
) -> SOARAssetOAuthClient:
    config = OAuthConfig(
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=asset.auth_url,
        token_endpoint=asset.token_url,
        redirect_uri=redirect_uri,
        scope=get_scopes(asset),
    )
    return SOARAssetOAuthClient(config, asset.auth_state)


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    logger.info(f"Testing connectivity with auth type: {asset.auth_type}")

    if asset.auth_type == "credentials":
        flow = ClientCredentialsFlow(
            asset.auth_state,
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            token_endpoint=asset.token_url,
            scope=get_scopes(asset),
        )
        flow.get_token()
        logger.info("Successfully obtained token via client credentials flow")

    elif asset.auth_type == "interactive":
        flow = AuthorizationCodeFlow(
            asset.auth_state,
            soar.get_asset_id(),
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            authorization_endpoint=asset.auth_url,
            token_endpoint=asset.token_url,
            redirect_uri=app.get_webhook_url("oauth_callback"),
            scope=get_scopes(asset),
        )

        auth_url = flow.get_authorization_url()
        logger.progress(f"Please authorize: {auth_url}")

        def on_progress(iteration: int) -> None:
            logger.info(f"Waiting for authorization... ({iteration})")

        flow.wait_for_authorization(on_progress=on_progress)
        logger.info("Successfully obtained token via authorization code flow")

    logger.info("Testing API connection...")
    with create_oauth_client(asset) as client:
        response = client.get(asset.domain)
        if response.is_success:
            logger.info("API connection verified successfully")
        else:
            logger.warning(
                f"API returned status {response.status_code}: {response.text}"
            )


@app.webhook("oauth_callback")
def oauth_callback(request: WebhookRequest[Asset]) -> WebhookResponse:
    query_params = {k: v[0] if v else "" for k, v in request.query.items()}

    if "error" in query_params:
        reason = query_params.get("error_description", "Unknown error")
        return WebhookResponse.text_response(
            content=f"Authorization failed: {reason}",
            status_code=400,
        )

    code = query_params.get("code")
    if not code:
        return WebhookResponse.text_response(
            content="Missing authorization code", status_code=400
        )

    oauth_client = get_oauth_client(request.asset)
    oauth_client.set_authorization_code(code)

    return WebhookResponse.text_response(
        content="Authorization successful! You can close this window.",
        status_code=200,
    )


class TestOutput(ActionOutput):
    status: str = OutputField(column_name="Status")
    response: str = OutputField(column_name="Response")


@app.action(action_type="investigate", verbose="Test API endpoint with OAuth")
def test_endpoint(params: Params, asset: Asset) -> TestOutput:
    with create_oauth_client(asset) as client:
        response = client.get(asset.domain)

    return TestOutput(
        status=str(response.status_code),
        response=response.text[:500] if response.text else "",
    )


if __name__ == "__main__":
    app.cli()
