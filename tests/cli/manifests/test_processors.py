import pytest
from unittest import mock

import json
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from soar_sdk.cli.manifests.processors import ManifestProcessor

if TYPE_CHECKING:
    from datetime import _TzInfo


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


def test_build_manifests():
    class mock_datetime(datetime):
        @classmethod
        def now(cls, tz: "_TzInfo | None" = timezone.utc) -> datetime:
            return datetime(year=2025, month=4, day=17, hour=12, tzinfo=tz)

    for test_app in ["tests/example_app", "tests/example_app_with_webhook"]:
        with mock.patch("soar_sdk.cli.manifests.processors.datetime", mock_datetime):
            processor = ManifestProcessor("example_app.json", project_context=test_app)
            app_meta = processor.build().to_json_manifest()

        with open(f"{test_app}/app.json") as expected_json:
            expected_meta = json.load(expected_json)

        assert app_meta == expected_meta
