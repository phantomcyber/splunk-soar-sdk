.. _static_token:

Static Token Authentication
===========================

For APIs that use API keys or pre-obtained tokens, use ``StaticTokenAuth`` with httpx:

.. code-block:: python

    from soar_sdk.auth import StaticTokenAuth
    import httpx

    auth = StaticTokenAuth(asset.api_key)

    with httpx.Client(auth=auth) as client:
        response = client.get("https://api.example.com/data")

Custom Token Types
------------------

By default, tokens are sent as ``Bearer`` tokens. For APIs that use different token types:

.. code-block:: python

    # For APIs expecting "ApiKey" prefix
    auth = StaticTokenAuth(asset.api_key, token_type="ApiKey")

    # For APIs expecting "Token" prefix
    auth = StaticTokenAuth(asset.api_key, token_type="Token")

This sends the header as ``Authorization: ApiKey <token>`` or ``Authorization: Token <token>``.

Custom Header Names
-------------------

For APIs that expect tokens in headers other than ``Authorization``:

.. code-block:: python

    # For APIs using X-API-Key header
    auth = StaticTokenAuth(asset.api_key, header_name="X-API-Key", token_type="")

    # For SOAR's ph-auth-token header
    auth = StaticTokenAuth(asset.token, header_name="ph-auth-token", token_type="")

Setting ``token_type=""`` sends the raw token without a prefix.
