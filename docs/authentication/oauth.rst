.. _oauth:

OAuth 2.0 Authentication
========================

The SDK provides OAuth 2.0 support for SOAR connectors, with automatic token management and secure storage.

Supported Flows
---------------

- **Authorization Code** (with PKCE support) - For user-delegated access
- **Client Credentials** - For service-to-service authentication
- **Certificate-based** - For certificate authentication (e.g., Microsoft Entra ID)

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

Using with HTTPX
----------------

For automatic token injection in HTTP requests, use ``create_oauth_client``:

.. code-block:: python

    from soar_sdk.auth import create_oauth_client

    with create_oauth_client(asset) as client:
        response = client.get("https://api.example.com/resource")

The factory infers ``client_id``, ``client_secret``, and ``token_endpoint`` from common
asset field names and returns a fully configured ``httpx.Client``.

For more control over the client, you can pass additional httpx options:

.. code-block:: python

    with create_oauth_client(asset, timeout=60.0, follow_redirects=True) as client:
        response = client.get("https://api.example.com/resource")

If you need just the auth handler (e.g., for async clients), use ``create_oauth_auth``:

.. code-block:: python

    from soar_sdk.auth import create_oauth_auth
    import httpx

    auth = create_oauth_auth(asset)

    with httpx.Client(auth=auth) as client:
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

- Fetches tokens on first request
- Refreshes expired tokens when a refresh token is available
- Retries on 401 responses

Token Storage
-------------

Tokens are automatically stored in the asset's ``auth_state`` and encrypted at rest. The SDK handles:

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
