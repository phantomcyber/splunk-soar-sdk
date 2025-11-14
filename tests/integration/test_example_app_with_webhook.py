from .soar_client import AppOnStackClient


def test_connectivity(webhook_app_client: AppOnStackClient):
    result = webhook_app_client.run_test_connectivity()
    assert result.success, f"Test connectivity failed: {result.message}"
