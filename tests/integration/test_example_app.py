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
    # Clean up any previous failed runs so they don't pollute the asset
    example_app_client.delete_ingested_containers()

    result = await example_app_client.run_poll()

    containers = example_app_client.get_ingested_containers()

    assert result.success, f"Polling failed: {result.message}"
    assert len(containers) == 1
    assert containers[0].get("artifact_count") == 2
    assert containers[0].get("name") == "Network Alerts"


def test_asset_state(example_app_client: AppOnStackClient):
    write_result = example_app_client.run_action("write state", {})
    assert write_result.success, f"State writing action failed: {write_result.message}"

    read_result = example_app_client.run_action("read state", {})
    assert read_result.success, f"State reading action failed: {read_result.message}"


@pytest.mark.onprem
def test_reverse_string_with_ab(example_app_client: AppOnStackClient):
    input_string = "AB Testing!"
    expected_output = input_string[::-1]

    result = example_app_client.run_action(
        "reverse string", {"input_string": input_string}
    )
    assert result.success, f"Action failed: {result.message}"

    data = result.data["data"][0]
    assert data.get("reversed_string") == expected_output
