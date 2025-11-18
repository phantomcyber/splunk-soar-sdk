import pytest

from .soar_client import AppOnStackClient


def test_connectivity(example_app_client: AppOnStackClient):
    result = example_app_client.run_test_connectivity()
    assert result.success, f"Test connectivity failed: {result.message}"


def test_reverse_string(example_app_client: AppOnStackClient):
    input_string = "Hello, world!"
    expected_output = input_string[::-1]

    result = example_app_client.run_action(
        "reverse string", {"input_string": input_string}
    )
    assert result.success, f"Action failed: {result.message}"

    data = result.data["data"][0]
    assert data.get("reversed_string") == expected_output
    assert data.get("original_string") == input_string
    assert data.get("_underscored_string") == f"{input_string}_{expected_output}"


@pytest.mark.asyncio
async def test_on_poll(example_app_client: AppOnStackClient):
    result = await example_app_client.run_poll()

    containers = example_app_client.phantom.find_containers_for_asset(
        asset_id=example_app_client.asset_id
    )
    for container in containers:
        example_app_client.phantom.delete_container(container["id"])

    assert result.success, f"Polling failed: {result.message}"
    assert len(containers) == 1
    assert containers[0].get("artifact_count") == 2
    assert containers[0].get("name") == "Network Alerts"


@pytest.mark.onprem
def test_reverse_string_with_ab(example_app_client: AppOnStackClient):
    """Test reverse string action with automation broker (on-prem simulation)."""
    input_string = "AB Testing!"
    expected_output = input_string[::-1]

    result = example_app_client.run_action(
        "reverse string", {"input_string": input_string}
    )
    assert result.success, f"Action failed: {result.message}"

    data = result.data["data"][0]
    assert data.get("reversed_string") == expected_output
