"""Integration tests for example app with webhook."""

import logging
import os

import pytest

from .soar_client import AppOnStackClient

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def webhook_app_client():
    """Create and set up an AppOnStackClient for example_app_with_webhook."""
    # Get configuration from environment
    phantom_url = os.environ.get("PHANTOM_URL")
    if not phantom_url:
        pytest.skip("PHANTOM_URL environment variable not set")

    # Extract host from URL
    host = phantom_url.replace("https://", "").replace("http://", "")

    username = os.environ.get("PHANTOM_USERNAME", "admin")
    password = os.environ.get("PHANTOM_PASSWORD", "password")

    # Webhook app asset configuration
    asset_config = {
        "base_url": "https://example.com",
        "api_key": "test_api_key",
        "key_header": "Authorization",
        "timezone": "America/New_York",
    }

    # Create client
    client = AppOnStackClient(
        host=host,
        username=username,
        password=password,
        app_name="example_app",  # Both apps have same name
        app_vendor="Splunk Inc.",
        asset_config=asset_config,
        verify_cert=False,
    )

    # Set up app (create asset and container)
    client.setup_app()

    yield client

    # Cleanup after all tests
    client.cleanup()


def test_connectivity(webhook_app_client: AppOnStackClient):
    """Test the 'test connectivity' action for the example app with webhook."""
    logger.info("Running test connectivity action for webhook app")

    result = webhook_app_client.run_test_connectivity()

    assert result.success, f"Test connectivity failed: {result.message}"

    logger.info("Test connectivity for webhook app passed successfully")
