from .soar_client import AppOnStackClient

import httpx
import pytest


def test_connectivity(webhook_app_client: AppOnStackClient):
    result = webhook_app_client.run_test_connectivity()
    assert result.success, f"Test connectivity failed: {result.message}"


@pytest.mark.xfail
def test_webhook_request(webhook_app_client: AppOnStackClient):
    webhook_app_client.enable_webhook({"requires_auth": False})

    response = httpx.get(
        f"{webhook_app_client.webhook_base_url}test_webhook",
        verify=webhook_app_client.phantom.verify_certs,
    )
    response.raise_for_status()
    assert response.text == "Webhook received"
