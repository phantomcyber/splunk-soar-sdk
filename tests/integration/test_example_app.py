"""Integration tests for example app."""

import json
import logging
import os
from pathlib import Path

import pytest

from .phantom_constants import ACTION_TEST_CONNECTIVITY, STATUS_SUCCESS
from .phantom_instance import PhantomInstance

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def phantom_instance():
    """Create a Phantom instance connection."""
    phantom_url = os.environ.get("PHANTOM_URL")
    phantom_username = os.environ.get("PHANTOM_USERNAME", "admin")
    phantom_password = os.environ.get("PHANTOM_PASSWORD", "password")

    if not phantom_url:
        pytest.skip("PHANTOM_URL environment variable not set")

    return PhantomInstance(
        base_url=phantom_url,
        ph_user=phantom_username,
        ph_pass=phantom_password,
        verify_certs=False,
    )


@pytest.fixture(scope="module")
def app_info(phantom_instance):
    """Get the example app info."""
    app_name = "Example App"
    app_vendor = "Splunk Inc."
    app_info_result = phantom_instance.get_app_info(name=app_name, vendor=app_vendor)

    assert app_info_result["count"] > 0, f"App '{app_name}' not found on instance"
    return app_info_result["data"][0]


@pytest.fixture(scope="module")
def asset_config():
    """Load asset configuration."""
    asset_file = Path(__file__).parent.parent / "example_app" / "example_asset.json"
    with open(asset_file) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def asset_id(phantom_instance, app_info, asset_config):
    """Create and configure an asset for the example app."""
    asset_name = f"example_app_integration_test_asset"

    # Build asset configuration
    asset_data = {
        "name": asset_name,
        "product_vendor": app_info["product_vendor"],
        "product_name": app_info["product_name"],
        "app_version": app_info["app_version"],
        "configuration": asset_config,
    }

    # Insert the asset
    asset_id = phantom_instance.insert_asset(asset_data, overwrite=True)
    logger.info(f"Created asset with ID: {asset_id}")

    yield asset_id

    # Cleanup: Delete the asset after tests
    try:
        phantom_instance.delete_asset(asset_id)
        logger.info(f"Deleted asset with ID: {asset_id}")
    except Exception as e:
        logger.warning(f"Failed to delete asset {asset_id}: {e}")


@pytest.fixture(scope="module")
def test_container(phantom_instance):
    """Create a test container for running actions."""
    label = "integration_test"

    # Ensure label exists
    try:
        phantom_instance.create_label(label)
    except Exception:
        pass  # Label might already exist

    container_id = phantom_instance.create_container(
        container_name="Integration Test Container",
        label=label,
        tags=["integration_test", "sdk"],
    )
    logger.info(f"Created container with ID: {container_id}")

    yield container_id

    # Cleanup: Delete the container after tests
    try:
        phantom_instance.delete_container(container_id)
        logger.info(f"Deleted container with ID: {container_id}")
    except Exception as e:
        logger.warning(f"Failed to delete container {container_id}: {e}")


def test_connectivity(phantom_instance, app_info, asset_id, test_container):
    """Test the 'test connectivity' action for the example app."""
    logger.info("Running test connectivity action")

    # Prepare action targets
    targets = [{"app_id": app_info["id"], "asset_id": asset_id}]

    # Run the test connectivity action
    action_id = phantom_instance.run_action(
        action=ACTION_TEST_CONNECTIVITY,
        container_id=test_container,
        targets=targets,
        name="integration_test_connectivity",
    )

    logger.info(f"Started action with ID: {action_id}")

    # Wait for action completion
    results = phantom_instance.wait_for_action_completion(action_id, timeout=300)

    # Verify results
    assert results is not None, "No results returned from action"
    assert "data" in results, "No data in action results"
    assert len(results["data"]) > 0, "No action runs in results"

    action_run = results["data"][0]
    assert "result_data" in action_run, "No result_data in action run"
    assert len(action_run["result_data"]) > 0, "No results in result_data"

    action_result = action_run["result_data"][0]
    assert action_result["status"] == STATUS_SUCCESS, (
        f"Test connectivity failed: {action_result.get('message', 'Unknown error')}"
    )

    logger.info("Test connectivity passed successfully")
