.. _oauth:

OAuth 2.0 Authentication
========================

The SDK provides OAuth 2.0 support for SOAR connectors, with automatic token management and secure storage.

Supported Flows
---------------

- **Authorization Code** (with PKCE support) - For user-delegated access
- **Client Credentials** - For service-to-service authentication
- **Certificate-based** - For certificate authentication (e.g., Microsoft Entra ID)
- **Resource Owner Password Credentials** - For legacy providers that require the password grant

Client Credentials Flow
-----------------------

The simplest flow for service accounts:

.. code-block:: python

    from soar_sdk.auth import ClientCredentialsFlow

    flow = ClientCredentialsFlow(
        auth_state=asset.auth_state,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        scope=["https://graph.microsoft.com/.default"],
    )

    token = flow.get_token()

Authorization Code Flow
-----------------------

For user-delegated access requiring browser authorization:

.. code-block:: python

    from soar_sdk.auth import AuthorizationCodeFlow

    flow = AuthorizationCodeFlow(
        auth_state=asset.auth_state,
        asset_id=soar.get_asset_id(),
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=asset.auth_url,
        token_endpoint=asset.token_url,
        redirect_uri=app.get_webhook_url("oauth_callback"),
        scope=["openid", "profile", "email"],
        use_pkce=True,
    )

    auth_url = flow.get_authorization_url()
    logger.progress(f"Please authorize: {auth_url}")
    token = flow.wait_for_authorization()

Password Grant
--------------

The Resource Owner Password Credentials (ROPC) grant lets a connector exchange a
user's username and password for an access token. Use it for legacy providers that
require it. `Current OAuth security guidance <https://www.rfc-editor.org/rfc/rfc9700#section-2.4>`_
advises against the grant because it exposes the user's password to the connector
and does not support interactive MFA. Prefer authorization code with PKCE for
user-delegated access or client credentials for service-to-service access.

Define the username and passwords on the asset and mark the secret fields as
sensitive. This example uses Test Connectivity to enroll and check API access.

.. code-block:: python

    import httpx2

    from soar_sdk.asset import AssetField, BaseAsset
    from soar_sdk.auth import OAuthBearerAuth, OAuthConfig, OAuthGrantType, SOARAssetOAuthClient


    class Asset(BaseAsset):
        token_endpoint: str = AssetField(description="OAuth token endpoint")
        client_id: str = AssetField(description="OAuth client ID")
        client_secret: str = AssetField(description="OAuth client secret", sensitive=True)
        username: str = AssetField(description="Service account username")
        password: str = AssetField(description="Service account password", sensitive=True)


    def password_grant_client(asset: Asset) -> SOARAssetOAuthClient:
        config = OAuthConfig(
            grant_type=OAuthGrantType.PASSWORD,
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            token_endpoint=asset.token_endpoint,
        )
        return SOARAssetOAuthClient(config, asset.auth_state)


    @app.test_connectivity()
    def test_connectivity(asset: Asset) -> None:
        oauth = password_grant_client(asset)
        oauth.fetch_token_with_password(username=asset.username, password=asset.password)
        with httpx2.Client(auth=OAuthBearerAuth(oauth)) as client:
            client.get("https://api.example.com/status").raise_for_status()

Use the same configuration with ``OAuthBearerAuth`` in actions to reuse and refresh
saved tokens. To acquire a token on demand, check for a valid token before making
the API call and explicitly exchange the password when a token is needed.

.. code-block:: python

    from soar_sdk.auth.client import (
        AuthorizationRequiredError,
        ConfigurationChangedError,
        TokenExpiredError,
    )


    def get_api_auth(asset: Asset) -> OAuthBearerAuth:
        oauth = password_grant_client(asset)
        try:
            oauth.get_valid_token()
        except (AuthorizationRequiredError, ConfigurationChangedError, TokenExpiredError):
            oauth.fetch_token_with_password(username=asset.username, password=asset.password)
        return OAuthBearerAuth(oauth)

A failed refresh raises ``TokenRefreshError``. The connector can surface the error
or explicitly start a new exchange. Run the exchange again after rotating the asset's
user credentials. The SDK saves tokens in encrypted asset auth state and uses the
user's password only during an explicit exchange.

The default client authentication method is ``client_secret_basic``. Set
``token_endpoint_auth_method="client_secret_post"`` for providers that accept
client credentials in the form body, such as `ServiceNow <https://www.servicenow.com/docs/r/platform-security/authentication/r_OAuthAPIRequestParameters.html>`_.
For a registered public client, set ``token_endpoint_auth_method="none"`` and
omit ``client_secret``. Use a verified HTTPS endpoint for token exchange and refresh.
If you supply your own HTTP client, configure it to verify server certificates.

Using with HTTPX2
-----------------

For automatic token injection in HTTP requests, use ``create_oauth_client``:

.. code-block:: python

    from soar_sdk.auth import create_oauth_client

    with create_oauth_client(asset) as client:
        response = client.get("https://api.example.com/resource")

The factory infers ``client_id``, ``client_secret``, and ``token_endpoint`` from common
asset field names and returns a fully configured ``httpx2.Client``.

For more control over the client, you can pass additional httpx2 options:

.. code-block:: python

    with create_oauth_client(asset, timeout=60.0, follow_redirects=True) as client:
        response = client.get("https://api.example.com/resource")

If you need just the auth handler (e.g., for async clients), use ``create_oauth_auth``:

.. code-block:: python

    import httpx2

    from soar_sdk.auth import create_oauth_auth

    auth = create_oauth_auth(asset)

    with httpx2.Client(auth=auth) as client:
        response = client.get("https://api.example.com/resource")

For custom configuration:

.. code-block:: python

    from soar_sdk.auth import OAuthBearerAuth, OAuthConfig, SOARAssetOAuthClient

    config = OAuthConfig(
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=asset.token_url,
        scope=["custom_scope"],
    )
    oauth_client = SOARAssetOAuthClient(config, asset.auth_state)
    auth = OAuthBearerAuth(oauth_client)

The auth handler automatically:

- Loads the saved token on the first request
- Refreshes expired tokens when a refresh token is available
- Retries on 401 responses

Token Storage
-------------

Tokens are automatically stored in the asset's ``auth_state``, which SOAR keeps encrypted at rest. The SDK handles:

- Token persistence across action runs
- Automatic refresh when tokens expire
- Credential change detection (forces re-authorization if client_id changes)

Certificate-based Authentication
---------------------------------

For certificate-based authentication (e.g., Microsoft Entra ID):

.. code-block:: python

    from soar_sdk.auth import CertificateCredentials, CertificateOAuthClient, OAuthConfig

    config = OAuthConfig(
        client_id=asset.client_id,
        token_endpoint=f"https://login.microsoftonline.com/{asset.tenant_id}/oauth2/v2.0/token",
        scope=["https://graph.microsoft.com/.default"],
    )

    certificate = CertificateCredentials(
        certificate_thumbprint=asset.cert_thumbprint,
        private_key=asset.private_key,
    )

    client = CertificateOAuthClient(config, asset.auth_state, certificate)
    token = client.fetch_token_with_certificate()

OAuth Callback Webhook
----------------------

For Authorization Code flow, register a webhook to receive the OAuth callback.
Use ``create_oauth_callback_handler`` to reduce boilerplate:

.. code-block:: python

    from soar_sdk.auth import create_oauth_callback_handler, OAuthConfig, SOARAssetOAuthClient

    def get_oauth_client(asset: Asset) -> SOARAssetOAuthClient:
        config = OAuthConfig(
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            token_endpoint=asset.token_url,
        )
        return SOARAssetOAuthClient(config, asset.auth_state)

    @app.webhook("oauth_callback")
    def oauth_callback(request: WebhookRequest[Asset]) -> WebhookResponse:
        return create_oauth_callback_handler(get_oauth_client)(request)

The factory handles error checking, code extraction, and success responses automatically.
