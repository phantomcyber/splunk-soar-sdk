from unittest import mock

from soar_sdk.cli.manifests.processors import ManifestProcessor


def test_manifest_processor_creating_json_from_meta():
    processor = ManifestProcessor(
        "example_app.json", project_context="./tests/example_app"
    )
    processor.save_json_manifest = mock.Mock()

    processor.create()

    processor.save_json_manifest.assert_called_once()
