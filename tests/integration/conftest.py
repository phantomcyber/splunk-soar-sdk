"""Pytest configuration for integration tests."""

import json
import logging
import os
from pathlib import Path

import pytest

from .soar_client import AppOnStackClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: Integration tests that require a live SOAR instance"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items."""
    # Add integration marker to all tests in this directory
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def example_app_client():
    """Create and set up an AppOnStackClient for example_app."""
    # Get configuration from environment
    phantom_url = os.environ.get("PHANTOM_URL")
    if not phantom_url:
        pytest.skip("PHANTOM_URL environment variable not set")

    # Extract host from URL
    host = phantom_url.replace("https://", "").replace("http://", "")

    username = os.environ.get("PHANTOM_USERNAME", "admin")
    password = os.environ.get("PHANTOM_PASSWORD", "password")

    # Load asset configuration
    asset_file = Path(__file__).parent.parent / "example_app" / "example_asset.json"
    with open(asset_file) as f:
        asset_config = json.load(f)

    # Create client
    client = AppOnStackClient(
        host=host,
        username=username,
        password=password,
        app_name="example_app",
        app_vendor="Splunk Inc.",
        asset_config=asset_config,
        verify_cert=False,
    )

    # Set up app (create asset and container)
    client.setup_app()

    yield client

    # Cleanup after all tests
    client.cleanup()
