from .soar_client import AppOnStackClient


def test_connectivity(example_app_client: AppOnStackClient):
    result = example_app_client.run_test_connectivity()
    assert result.success, f"Test connectivity failed: {result.message}"


def test_reverse_string(example_app_client: AppOnStackClient):
    input_string = "Hello, world!"
    expected_output = input_string[::-1]

    result = example_app_client.run_action(
        "reverse_string", {"input_string": input_string}
    )
    assert result.success, f"Action failed: {result.message}"
    assert result.data.get("original_string") == input_string
    assert result.data.get("reversed_string") == expected_output
    assert result.data.get("underscored_string") == f"{input_string}_{expected_output}"


def test_on_poll(example_app_client: AppOnStackClient):
    result = example_app_client.run_poll({})

    assert result.success, f"Polling failed: {result.message}"
    assert len(result.data) == 2
