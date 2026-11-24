.. _basic_auth:

Basic Authentication
====================

For APIs that use HTTP Basic Authentication (username/password):

.. code-block:: python

    import httpx2

    from soar_sdk.auth import BasicAuth

    auth = BasicAuth(asset.username, asset.password)

    with httpx2.Client(auth=auth) as client:
        response = client.get("https://api.example.com/data")

This sends the ``Authorization: Basic <base64(username:password)>`` header with each request.
