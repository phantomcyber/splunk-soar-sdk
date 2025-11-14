import json
import os
from pathlib import Path

import pytest

from .soar_client import AppOnStackClient


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: Integration tests that require a live SOAR instance"
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def example_app_client():
    phantom_url = os.environ.get("PHANTOM_URL")
    if not phantom_url:
        pytest.skip("PHANTOM_URL environment variable not set")

    host = phantom_url.replace("https://", "").replace("http://", "")

    username = os.environ.get("PHANTOM_USERNAME", "admin")
    password = os.environ.get("PHANTOM_PASSWORD", "password")

    asset_file = Path(__file__).parent.parent / "example_app" / "example_asset.json"
    with open(asset_file) as f:
        asset_config = json.load(f)

    client = AppOnStackClient(
        host=host,
        username=username,
        password=password,
        app_name="example_app",
        app_vendor="Splunk Inc.",
        asset_config=asset_config,
        verify_cert=False,
    )

    client.setup_app()

    yield client

    client.cleanup()
