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

        test_markers = [marker.name for marker in item.iter_markers()]
        force_automation_broker = False
        if cls := item.cls:
            force_automation_broker = getattr(cls, "force_automation_broker", False)

        if pytest.mark.onprem.name in test_markers or force_automation_broker:
            item.add_marker(pytest.mark.require_ab)


@pytest.fixture(scope="session")
def automation_broker_name(request):
    force_ab = os.environ.get("FORCE_AUTOMATION_BROKER", "").lower() in (
        "true",
        "1",
        "yes",
    )
    test_markers = [marker.name for marker in request.node.iter_markers()]
    requires_ab = (
        pytest.mark.require_ab.name in test_markers
        or pytest.mark.onprem.name in test_markers
    )

    if force_ab or requires_ab:
        ab_name = os.environ.get("AUTOMATION_BROKER_NAME")
        if ab_name:
            return ab_name
    return None


@pytest.fixture(scope="session")
def example_app_client(request, automation_broker_name):
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
        automation_broker_name=automation_broker_name,
    )

    client.setup_app()

    yield client

    client.cleanup()


@pytest.fixture(scope="session")
def webhook_app_client(request, automation_broker_name):
    phantom_url = os.environ.get("PHANTOM_URL")
    if not phantom_url:
        pytest.skip("PHANTOM_URL environment variable not set")

    host = phantom_url.replace("https://", "").replace("http://", "")

    username = os.environ.get("PHANTOM_USERNAME", "admin")
    password = os.environ.get("PHANTOM_PASSWORD", "password")

    asset_file = (
        Path(__file__).parent.parent / "example_app_with_webhook" / "example_asset.json"
    )
    with open(asset_file) as f:
        asset_config = json.load(f)

    client = AppOnStackClient(
        host=host,
        username=username,
        password=password,
        app_name="example_app with webhook",
        app_vendor="Splunk Inc.",
        asset_config=asset_config,
        verify_cert=False,
        automation_broker_name=automation_broker_name,
    )

    client.setup_app()

    yield client

    client.cleanup()
