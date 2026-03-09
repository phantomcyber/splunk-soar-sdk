"""Integration tests for ES poll.

Verifies that on_es_poll runs successfully and creates findings,
both with and without automation broker.
"""

import pytest

from .soar_client import AppOnStackClient


@pytest.mark.asyncio
async def test_es_poll_without_ab(es_app_client: AppOnStackClient):
    """Run ES poll without automation broker."""
    es_app_client.delete_ingested_containers()

    result = await es_app_client.run_poll()
    assert result.success, f"ES poll failed: {result.message}"

    containers = es_app_client.get_ingested_containers()
    assert len(containers) >= 1, "ES poll should have created at least one container"


@pytest.mark.asyncio
async def test_es_poll_with_ab(es_app_client_with_ab: AppOnStackClient):
    """Run ES poll with automation broker."""
    es_app_client_with_ab.delete_ingested_containers()

    result = await es_app_client_with_ab.run_poll()
    assert result.success, f"ES poll with AB failed: {result.message}"

    containers = es_app_client_with_ab.get_ingested_containers()
    assert len(containers) >= 1, (
        "ES poll with AB should have created at least one container"
    )
