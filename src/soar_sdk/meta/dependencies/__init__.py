__lazy_modules__ = {
    "soar_sdk.meta.dependencies.constants",
    "soar_sdk.meta.dependencies.lock",
    "soar_sdk.meta.dependencies.package",
    "soar_sdk.meta.dependencies.sources",
    "soar_sdk.meta.dependencies.utils",
    "soar_sdk.meta.dependencies.uv_models",
    "soar_sdk.meta.dependencies.wheels",
}

from soar_sdk.meta.dependencies.constants import (
    DEPENDENCIES_TO_BUILD,
    DEPENDENCIES_TO_REJECT,
    DEPENDENCIES_TO_SKIP,
)
from soar_sdk.meta.dependencies.lock import UvLock
from soar_sdk.meta.dependencies.package import UvPackage
from soar_sdk.meta.dependencies.sources import (
    UvSourceDirectory,
    UvSourceDistribution,
    UvWheel,
)
from soar_sdk.meta.dependencies.utils import normalize_package_name
from soar_sdk.meta.dependencies.uv_models import UvDependency, UvSource
from soar_sdk.meta.dependencies.wheels import DependencyList, DependencyWheel

__all__ = [
    "DEPENDENCIES_TO_BUILD",
    "DEPENDENCIES_TO_REJECT",
    "DEPENDENCIES_TO_SKIP",
    "DependencyList",
    "DependencyWheel",
    "UvDependency",
    "UvLock",
    "UvPackage",
    "UvSource",
    "UvSourceDirectory",
    "UvSourceDistribution",
    "UvWheel",
    "normalize_package_name",
]
