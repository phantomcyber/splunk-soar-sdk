"""Integration tests for example app."""

import logging

from .soar_client import AppOnStackClient

logger = logging.getLogger(__name__)


def test_connectivity(example_app_client: AppOnStackClient):
    """Test the 'test connectivity' action for the example app."""
    logger.info("Running test connectivity action")

    result = example_app_client.run_test_connectivity()

    assert result.success, f"Test connectivity failed: {result.message}"

    logger.info("Test connectivity passed successfully")
