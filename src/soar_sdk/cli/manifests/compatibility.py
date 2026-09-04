from collections.abc import Callable, Iterable
from dataclasses import dataclass

from packaging.version import Version

from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.meta.app import AppMeta


@dataclass(frozen=True)
class FeatureRequirement:
    """Minimum SOAR version required when a manifest feature is used."""

    minimum_phantom_version: str
    is_used: Callable[[AppMeta], bool]

    def __post_init__(self) -> None:
        """Reject compatibility rules older than the SDK's supported SOAR versions."""
        remove_when_soar_newer_than(
            self.minimum_phantom_version,
            "Remove this obsolete feature requirement.",
        )


def _configuration_uses_data_type(data_type: str) -> Callable[[AppMeta], bool]:
    def is_used(app_meta: AppMeta) -> bool:
        return any(
            field.get("data_type") == data_type
            for field in app_meta.configuration.values()
        )

    return is_used


FEATURE_REQUIREMENTS = (
    FeatureRequirement(
        minimum_phantom_version="8.8.0",
        is_used=_configuration_uses_data_type("python_script"),
    ),
)


def resolve_minimum_phantom_version(
    app_meta: AppMeta,
    feature_requirements: Iterable[FeatureRequirement] = FEATURE_REQUIREMENTS,
) -> str:
    """Raise an app's minimum SOAR version for the features in its manifest."""
    minimum_phantom_version = app_meta.min_phantom_version

    for requirement in feature_requirements:
        if requirement.is_used(app_meta) and Version(minimum_phantom_version) < Version(
            requirement.minimum_phantom_version
        ):
            minimum_phantom_version = requirement.minimum_phantom_version

    return minimum_phantom_version
