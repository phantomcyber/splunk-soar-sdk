from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import httpx

from soar_sdk.auth.client import SOARAssetOAuthClient
from soar_sdk.auth.httpx_auth import OAuthBearerAuth
from soar_sdk.auth.models import OAuthConfig

if TYPE_CHECKING:
    from collections.abc import Iterator

    from soar_sdk.asset import BaseAsset
    from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse


def create_oauth_auth(
    asset: BaseAsset,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    token_endpoint: str | None = None,
    scope: list[str] | None = None,
    auto_refresh: bool = True,
) -> OAuthBearerAuth:
    """Create an OAuthBearerAuth from an asset with defaults."""
    resolved_client_id = client_id or getattr(asset, "client_id", None)
    if not resolved_client_id:
        msg = "client_id must be provided or available as asset.client_id"
        raise ValueError(msg)

    resolved_token_endpoint = (
        token_endpoint
        or getattr(asset, "token_endpoint", None)
        or getattr(asset, "token_url", None)
    )
    if not resolved_token_endpoint:
        msg = "token_endpoint must be provided or available as asset.token_endpoint or asset.token_url"
        raise ValueError(msg)

    resolved_scope = scope
    if resolved_scope is None:
        asset_scope = getattr(asset, "scope", None)
        if isinstance(asset_scope, str) and asset_scope:
            resolved_scope = asset_scope.split()
        elif isinstance(asset_scope, list):
            resolved_scope = asset_scope

    config = OAuthConfig(
        client_id=resolved_client_id,
        client_secret=client_secret or getattr(asset, "client_secret", None),
        token_endpoint=resolved_token_endpoint,
        scope=resolved_scope,
    )
    oauth_client = SOARAssetOAuthClient(config, asset.auth_state)
    return OAuthBearerAuth(oauth_client, auto_refresh=auto_refresh)


@contextmanager
def create_oauth_client(
    asset: BaseAsset,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    token_endpoint: str | None = None,
    scope: list[str] | None = None,
    auto_refresh: bool = True,
    timeout: float = 30.0,
    **httpx_kwargs: Any,  # noqa: ANN401
) -> Iterator[httpx.Client]:
    """Create an httpx.Client with OAuth authentication from an asset."""
    auth = create_oauth_auth(
        asset,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint,
        scope=scope,
        auto_refresh=auto_refresh,
    )
    with httpx.Client(auth=auth, timeout=timeout, **httpx_kwargs) as client:
        yield client


def create_oauth_callback_handler(
    get_oauth_client: Callable[[Any], SOARAssetOAuthClient],
    *,
    success_message: str = "Authorization successful! You can close this window.",
) -> Callable[[WebhookRequest], WebhookResponse]:
    """Factory for creating standard OAuth callback webhook handlers."""
    from soar_sdk.webhooks.models import WebhookResponse

    def oauth_callback(request: WebhookRequest) -> WebhookResponse:
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
                content="Missing authorization code",
                status_code=400,
            )

        oauth_client = get_oauth_client(request.asset)
        oauth_client.set_authorization_code(code)

        return WebhookResponse.text_response(
            content=success_message,
            status_code=200,
        )

    return oauth_callback
