.. _oauth:

OAuth 2.0 Authentication
========================

The SDK provides OAuth 2.0 support for SOAR connectors, with automatic token management and secure storage via the asset's ``auth_state``.

Supported Flows
---------------

- **Authorization Code** (with PKCE support) - For user-delegated access
- **Client Credentials** - For service-to-service authentication
- **Certificate-based** - For certificate authentication (e.g., Microsoft Entra ID)

Client Credentials Flow
-----------------------

The simplest flow for service accounts:

.. code-block:: python

    from soar_sdk.oauth import ClientCredentialsFlow

    flow = ClientCredentialsFlow(
        auth_state=asset.auth_state,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        scope=["https://graph.microsoft.com/.default"],
    )

    token = flow.get_token()
    # Use token.access_token for API calls

Authorization Code Flow
-----------------------

For user-delegated access requiring browser authorization:

.. code-block:: python

    from soar_sdk.oauth import AuthorizationCodeFlow

    flow = AuthorizationCodeFlow(
        auth_state=asset.auth_state,
        asset_id=soar.get_asset_id(),
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=asset.auth_url,
        token_endpoint=asset.token_url,
        redirect_uri=redirect_uri,
        scope=["openid", "profile", "email"],
        use_pkce=True,  # Recommended for security
    )

    # In test_connectivity action:
    auth_url = flow.get_authorization_url()
    print(f"Please visit: {auth_url}")
    token = flow.wait_for_authorization()

    # In subsequent actions:
    token = flow.get_token()

Using with HTTPX
----------------

For automatic token injection in HTTP requests:

.. code-block:: python

    from soar_sdk.oauth import ClientCredentialsFlow, OAuthClientCredentialsAuth
    import httpx

    flow = ClientCredentialsFlow(...)
    auth = OAuthClientCredentialsAuth(flow.client)

    with httpx.Client(auth=auth) as client:
        response = client.get("https://api.example.com/resource")

The auth handler automatically:

- Fetches tokens on first request
- Refreshes expired tokens
- Retries on 401 responses

Token Storage
-------------

Tokens are automatically stored in the asset's ``auth_state`` and encrypted at rest. The SDK handles:

- Token persistence across action runs
- Automatic refresh when tokens expire
- Credential change detection (forces re-authorization if client_id changes)

OAuth Callback Webhook
----------------------

For Authorization Code flow, the SDK can handle the OAuth callback. Register a webhook in your app:

.. code-block:: python

    @app.webhook("/oauth/callback")
    def oauth_callback(request: WebhookRequest) -> WebhookResponse:
        flow = AuthorizationCodeFlow(...)
        code = request.query.get("code")
        if code:
            flow.set_authorization_code(code)
        return WebhookResponse(status_code=200, body="Authorization complete")
