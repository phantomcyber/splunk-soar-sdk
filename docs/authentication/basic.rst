.. _basic_auth:

Basic Authentication
====================

For APIs that use HTTP Basic Authentication (username/password):

.. code-block:: python

    from soar_sdk.auth import BasicAuth
    import httpx

    auth = BasicAuth(asset.username, asset.password)

    with httpx.Client(auth=auth) as client:
        response = client.get("https://api.example.com/data")

This sends the ``Authorization: Basic <base64(username:password)>`` header with each request.
