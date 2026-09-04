import pytest

from soar_sdk.asset import AssetFieldSpecification, FieldCategory
from soar_sdk.cli.manifests.compatibility import (
    FeatureRequirement,
    resolve_minimum_phantom_version,
)
from soar_sdk.compat import MIN_PHANTOM_VERSION
from soar_sdk.meta.app import AppMeta


def _app_meta(
    min_phantom_version: str,
    configuration: dict[str, AssetFieldSpecification] | None = None,
) -> AppMeta:
    return AppMeta(
        description="",
        app_version="1.0.0",
        license="",
        min_phantom_version=min_phantom_version,
        package_name="phantom_test",
        project_name="test",
        configuration=configuration or {},
    )


@pytest.mark.parametrize(
    ("min_phantom_version", "expected"),
    (("7.0.0", "8.8.0"), ("8.8.0", "8.8.0"), ("9.0.0", "9.0.0")),
)
def test_python_script_minimum_phantom_version(
    min_phantom_version: str, expected: str
) -> None:
    app_meta = _app_meta(
        min_phantom_version,
        configuration={
            "parser": {
                "data_type": "python_script",
                "category": FieldCategory.CONNECTIVITY,
            }
        },
    )

    assert resolve_minimum_phantom_version(app_meta) == expected


def test_unused_feature_does_not_change_minimum_phantom_version() -> None:
    app_meta = _app_meta(
        "7.0.0",
        configuration={
            "certificate": {
                "data_type": "file",
                "category": FieldCategory.CONNECTIVITY,
            }
        },
    )

    assert resolve_minimum_phantom_version(app_meta) == "7.0.0"


def test_highest_used_feature_minimum_phantom_version_wins() -> None:
    def feature_is_used(_: AppMeta) -> bool:
        return True

    app_meta = _app_meta("7.0.0")
    requirements = (
        FeatureRequirement("9.0.0", feature_is_used),
        FeatureRequirement("8.0.0", feature_is_used),
    )

    assert resolve_minimum_phantom_version(app_meta, requirements) == "9.0.0"


def test_feature_requirement_rejects_version_below_sdk_minimum() -> None:
    def feature_is_used(_: AppMeta) -> bool:
        return True

    with pytest.raises(RuntimeError, match="Remove this obsolete feature requirement"):
        FeatureRequirement("6.0.0", feature_is_used)


@pytest.mark.parametrize("minimum_phantom_version", (MIN_PHANTOM_VERSION, "8.0.0"))
def test_feature_requirement_accepts_supported_version(
    minimum_phantom_version: str,
) -> None:
    def feature_is_used(_: AppMeta) -> bool:
        return True

    FeatureRequirement(minimum_phantom_version, feature_is_used)
