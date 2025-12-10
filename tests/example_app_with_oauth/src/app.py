from collections.abc import Iterator

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.logging import getLogger
from soar_sdk.oauth import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
    OAuthBearerAuth,
    SOARAssetOAuthClient,
)
from soar_sdk.oauth.models import OAuthConfig
from soar_sdk.params import Param, Params
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

logger = getLogger()

APP_NAME = "example_app_with_oauth"
APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf56"
BASE_URL = "https://graph.microsoft.com"
DEFAULT_SCOPE = "https://graph.microsoft.com/.default"


class Asset(BaseAsset):
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
    tenant_id: str = AssetField(description="Azure AD Tenant ID")
    soar_external_host: str = AssetField(
        default="",
        required=False,
        description="External SOAR hostname for OAuth callback. Leave empty to auto-detect.",
    )

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    @property
    def auth_url(self) -> str:
        return (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"
        )


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
    min_phantom_version="6.2.2.134",
).enable_webhooks(default_requires_auth=False)


def get_webhook_redirect_uri(soar: SOARClient, asset: Asset) -> str:
    from urllib.parse import urlparse

    if asset.soar_external_host:
        webhook_base = f"https://{asset.soar_external_host}:3500"
    else:
        base_url = soar.get_soar_base_url().rstrip("/")
        parsed = urlparse(base_url)
        webhook_base = f"{parsed.scheme}://{parsed.hostname}:3500"

    asset_id = soar.get_asset_id()
    return f"{webhook_base}/webhook/{APP_NAME}_{APP_ID}/{asset_id}/oauth_callback"


def get_oauth_client(
    asset: Asset, redirect_uri: str | None = None
) -> SOARAssetOAuthClient:
    config = OAuthConfig(
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=asset.auth_url,
        token_endpoint=asset.token_url,
        redirect_uri=redirect_uri,
        scope=[DEFAULT_SCOPE],
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
            scope=[DEFAULT_SCOPE],
        )
        token = flow.get_token()
        logger.info("Successfully obtained token via client credentials flow")

    elif asset.auth_type == "interactive":
        asset_id = soar.get_asset_id()
        redirect_uri = get_webhook_redirect_uri(soar, asset)

        flow = AuthorizationCodeFlow(
            asset.auth_state,
            asset_id,
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            authorization_endpoint=asset.auth_url,
            token_endpoint=asset.token_url,
            redirect_uri=redirect_uri,
            scope=[DEFAULT_SCOPE],
        )

        auth_url = flow.get_authorization_url()
        logger.progress(f"Please authorize: {auth_url}")

        def on_progress(iteration: int) -> None:
            logger.info(f"Waiting for authorization... ({iteration})")

        token = flow.wait_for_authorization(on_progress=on_progress)
        logger.info("Successfully obtained token via authorization code flow")

    logger.info("Testing API connection...")
    with httpx.Client(
        transport=httpx.HTTPTransport(verify=False, local_address="0.0.0.0"),
        timeout=30.0,
    ) as client:
        response = client.get(
            f"{BASE_URL}/v1.0/me",
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        if response.status_code == 200:
            logger.info("API connection verified successfully")
        else:
            logger.warning(
                f"API returned status {response.status_code}: {response.text}"
            )


@app.webhook("oauth_callback")
def oauth_callback(request: WebhookRequest[Asset]) -> WebhookResponse:
    query_params = {k: v[0] if v else "" for k, v in request.query.items()}

    if "error" in query_params:
        error_description = query_params.get("error_description", "No description")
        return WebhookResponse.text_response(
            content=f"Authorization failed: {error_description}",
            status_code=400,
        )

    code = query_params.get("code")
    asset_id = query_params.get("state")

    if not code:
        return WebhookResponse.text_response(
            content="Missing authorization code", status_code=400
        )
    if not asset_id:
        return WebhookResponse.text_response(
            content="Missing state parameter", status_code=400
        )

    # Store code in state using the OAuth client
    oauth_client = get_oauth_client(request.asset)
    oauth_client.set_authorization_code(code)

    return WebhookResponse.text_response(
        content="Authorization successful! You can close this window.",
        status_code=200,
    )


class UserInfoOutput(ActionOutput):
    display_name: str = OutputField(column_name="Display Name")
    email: str = OutputField(column_name="Email")
    id: str = OutputField(column_name="User ID")


@app.action(action_type="investigate", verbose="Get information about the current user")
def get_current_user(params: Params, asset: Asset) -> UserInfoOutput:
    oauth_client = get_oauth_client(asset)
    auth = OAuthBearerAuth(oauth_client)

    with httpx.Client(
        auth=auth,
        transport=httpx.HTTPTransport(verify=False, local_address="0.0.0.0"),
        timeout=30.0,
    ) as client:
        response = client.get(f"{BASE_URL}/v1.0/me")
        response.raise_for_status()
        data = response.json()

    return UserInfoOutput(
        display_name=data.get("displayName", ""),
        email=data.get("mail", data.get("userPrincipalName", "")),
        id=data.get("id", ""),
    )


class ListUsersParams(Params):
    limit: int = Param(default=10, description="Maximum number of users to return")


class UserOutput(ActionOutput):
    display_name: str = OutputField(column_name="Display Name")
    email: str = OutputField(column_name="Email")
    id: str = OutputField(column_name="User ID")


@app.action(action_type="investigate", verbose="List users in the directory")
def list_users(params: ListUsersParams, asset: Asset) -> Iterator[UserOutput]:
    oauth_client = get_oauth_client(asset)
    auth = OAuthBearerAuth(oauth_client)

    with httpx.Client(
        auth=auth,
        transport=httpx.HTTPTransport(verify=False, local_address="0.0.0.0"),
        timeout=30.0,
    ) as client:
        response = client.get(f"{BASE_URL}/v1.0/users", params={"$top": params.limit})
        response.raise_for_status()
        data = response.json()

    for user in data.get("value", []):
        yield UserOutput(
            display_name=user.get("displayName", ""),
            email=user.get("mail", user.get("userPrincipalName", "")),
            id=user.get("id", ""),
        )


if __name__ == "__main__":
    app.cli()
