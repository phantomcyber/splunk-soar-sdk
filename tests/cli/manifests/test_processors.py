import pytest
from unittest import mock

import json
from datetime import datetime

import pytest_mock

from soar_sdk.cli.manifests.processors import ManifestProcessor
from soar_sdk.compat import UPDATE_TIME_FORMAT


def test_manifest_processor_creating_json_from_meta(mocker: pytest_mock.MockerFixture):
    processor = ManifestProcessor(
        "example_app.json", project_context="./tests/example_app"
    )

    save_json_manifest = mocker.patch.object(processor, "save_json_manifest")
    processor.create()
    save_json_manifest.assert_called_once()


@mock.patch("builtins.open", new_callable=mock.mock_open, read_data="data")
def test_save_json(open_mock):
    processor = ManifestProcessor(
        "example_app.json", project_context="./tests/example_app"
    )

    with mock.patch("json.dump") as mock_json:
        processor.save_json_manifest(mock.Mock())

    mock_json.assert_called_once()


@pytest.mark.parametrize(
    "main_module, dot_path",
    (
        ("src/app.py:app", "src.app"),
        ("src/modules/app.py:app", "src.modules.app"),
        ("src/app:app", "src.app"),
        ("src/app.pyc:app", "src.app"),
    ),
)
def test_get_module_dot_path(main_module, dot_path):
    assert ManifestProcessor.get_module_dot_path(main_module) == dot_path


@pytest.mark.parametrize("app", ("example_app", "example_app_with_webhook"))
def test_build_manifests(app: str):
    test_app = f"tests/{app}"
    processor = ManifestProcessor("example_app.json", project_context=test_app)
    app_meta = processor.build().to_json_manifest()

    with open(f"{test_app}/app.json") as expected_json:
        expected_meta = json.load(expected_json)

    # Verify the update time is there and is a valid datetime
    assert "utctime_updated" in app_meta
    try:
        datetime.strptime(  #  noqa: DTZ007
            app_meta["utctime_updated"], UPDATE_TIME_FORMAT
        )
    except Exception as e:
        pytest.fail(f"utctime_updated is not a valid datetime: {e}")

    # Now, to avoid having to update tests all the time, we set it to a fixed value
    app_meta["utctime_updated"] = expected_meta["utctime_updated"]

    assert app_meta == expected_meta
