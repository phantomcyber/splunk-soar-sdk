import json
from datetime import datetime
from unittest import mock

import pytest
import pytest_mock
import toml
from packaging.requirements import Requirement

from soar_sdk.cli.manifests.processors import ManifestProcessor
from soar_sdk.compat import UPDATE_TIME_FORMAT
from soar_sdk.meta.dependencies import DEPENDENCIES_TO_SKIP, normalize_package_name

DEPENDENCY_SECTIONS = ("pip313_dependencies", "pip314_dependencies")
PYTHON_DEPENDENCY_PREFIX = {
    "pip313_dependencies": "python313",
    "pip314_dependencies": "python314",
}


def _without_resolved_dependencies(manifest: dict) -> dict:
    return {
        key: value for key, value in manifest.items() if key not in DEPENDENCY_SECTIONS
    }


def _assert_wheel_path_is_well_formed(path: str, dependency_section: str) -> None:
    assert path.startswith("wheels/")
    assert path.endswith(".whl")

    path_parts = path.split("/")
    if path_parts[1] == "shared":
        return

    assert path_parts[1] == PYTHON_DEPENDENCY_PREFIX[dependency_section]


def _assert_dependency_section_is_well_formed(
    manifest: dict, dependency_section: str
) -> None:
    dependency_list = manifest[dependency_section]["wheel"]
    assert dependency_list

    for dependency in dependency_list:
        assert dependency["module"]
        assert dependency["input_file"]
        _assert_wheel_path_is_well_formed(dependency["input_file"], dependency_section)

        input_file_aarch64 = dependency.get("input_file_aarch64")
        if input_file_aarch64 is not None:
            _assert_wheel_path_is_well_formed(input_file_aarch64, dependency_section)


def _assert_direct_dependencies_are_present(
    manifest: dict, pyproject_path: str
) -> None:
    pyproject_data = toml.load(pyproject_path)
    direct_dependencies = {
        normalize_package_name(Requirement(dependency).name)
        for dependency in pyproject_data["project"]["dependencies"]
    } - DEPENDENCIES_TO_SKIP

    for dependency_section in DEPENDENCY_SECTIONS:
        manifest_dependencies = {
            normalize_package_name(dependency["module"])
            for dependency in manifest[dependency_section]["wheel"]
        }
        assert direct_dependencies <= manifest_dependencies


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


@pytest.mark.parametrize(
    "app",
    ("example_app", "example_app_with_webhook", "example_app_plaintext_state"),
)
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

    for manifest in (app_meta, expected_meta):
        for dependency_section in DEPENDENCY_SECTIONS:
            _assert_dependency_section_is_well_formed(manifest, dependency_section)
        _assert_direct_dependencies_are_present(manifest, f"{test_app}/pyproject.toml")

    assert _without_resolved_dependencies(app_meta) == _without_resolved_dependencies(
        expected_meta
    )
