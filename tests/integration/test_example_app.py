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


# TODO: implement this next
# def test_on_poll(example_app_client: AppOnStackClient):
#     result = example_app_client.run_poll({})  # noqa: ERA001

#     assert result.success, f"Polling failed: {result.message}"  # noqa: ERA001
#     assert len(result.data) == 2  # noqa: ERA001
