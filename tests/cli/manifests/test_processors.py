from unittest import mock

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
