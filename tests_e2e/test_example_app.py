from .conftest import AppOnStackClient


def test_connectivity(example_app_installed: AppOnStackClient):
    result = example_app_installed.run_test_connectivity()
    assert result.success


def test_reverse_string(example_app_installed: AppOnStackClient):
    result = example_app_installed.run_action(
        "reverse_string", {"input_string": "hello world!"}
    )
    assert result.output[0].output_string == "!dlrow olleh"


def test_polling(example_app_installed: AppOnStackClient):
    rows = example_app_installed.run_poll({"count": 2})
    assert len(rows) == 2
