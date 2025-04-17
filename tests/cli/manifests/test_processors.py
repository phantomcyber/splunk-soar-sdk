import pytest
from unittest import mock

import json
from datetime import datetime, timezone

from soar_sdk.cli.manifests.processors import ManifestProcessor


def test_manifest_processor_creating_json_from_meta():
    processor = ManifestProcessor(
        "example_app.json", project_context="./tests/example_app"
    )
    processor.save_json_manifest = mock.Mock()

    processor.create()

    processor.save_json_manifest.assert_called_once()


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


def test_build_manifest():
    class mock_datetime(datetime):
        @classmethod
        def now(cls, tzinfo: timezone = timezone.utc) -> datetime:
            return datetime(year=2025, month=4, day=17, hour=12, tzinfo=tzinfo)

    with mock.patch("soar_sdk.cli.manifests.processors.datetime", mock_datetime):
        processor = ManifestProcessor(
            "example_app.json", project_context="./tests/example_app"
        )
        app_meta = processor.build().dict()

    with open("tests/example_app/app.json") as expected_json:
        expected_meta = json.load(expected_json)

    assert app_meta == expected_meta
