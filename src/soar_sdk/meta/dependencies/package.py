from logging import getLogger
from typing import ClassVar

from pydantic import BaseModel, Field

from .constants import DEPENDENCIES_TO_BUILD
from .sources import UvSourceDirectory, UvSourceDistribution, UvWheel
from .utils import normalize_package_name
from .uv_models import UvDependency, UvSource
from .wheels import DependencyWheel

logger = getLogger("soar_sdk.meta.dependencies")


class UvPackage(BaseModel):
    """Represents a Python package loaded from the uv lock."""

    name: str
    version: str
    dependencies: list[UvDependency] = []
    optional_dependencies: dict[str, list[UvDependency]] = Field(
        default_factory=dict, alias="optional-dependencies"
    )
    wheels: list[UvWheel] = []
    sdist: UvSourceDistribution | None = None
    source: UvSource

    def _find_wheel(
        self,
        abi_precedence: list[str],
        python_precedence: list[str],
        platform_precedence: list[str],
    ) -> UvWheel:
        """Search the list of wheels in uv.lock for the given package and return the first one that matches the given constraints.

        Constraints are evaluated in the order: ABI tag -> Python tag -> platform tag.
        If multiple wheels match a given triple, the first one in uv.lock is returned.
        If no wheel satisfies the given constraints, a FileNotFoundError is raised.
        """
        for abi in abi_precedence:
            abi_wheels = [wheel for wheel in self.wheels if abi in wheel.abi_tags]
            for python in python_precedence:
                python_wheels = self._filter_python_wheels(abi_wheels, python, abi)
                for platform in platform_precedence:
                    platform_wheels = [
                        wheel
                        for wheel in python_wheels
                        if platform in wheel.platform_tags
                    ]
                    if len(platform_wheels) > 0:
                        return platform_wheels[0]

        raise FileNotFoundError(
            f"Could not find a suitable wheel for {self.name=}, {self.version=}, {abi_precedence=}, {python_precedence=}, {platform_precedence=}"
        )

    def _filter_python_wheels(
        self, wheels: list[UvWheel], target_python: str, abi: str
    ) -> list[UvWheel]:
        """Filter and sort wheels by Python version compatibility.

        For abi3 wheels, prefers the highest compatible minimum version
        (e.g., cp311-abi3 over cp38-abi3 for Python 3.13).
        """
        compatible = [
            wheel
            for wheel in wheels
            if self._is_python_compatible(wheel, target_python, abi)
        ]

        # For abi3 wheels, prefer highest minimum version (closest to target)
        if abi == "abi3" and compatible:
            compatible = sorted(
                compatible,
                key=lambda w: max(
                    (int(tag[2:]) for tag in w.python_tags if tag.startswith("cp")),
                    default=0,
                ),
                reverse=True,
            )

        return compatible

    def _is_python_compatible(
        self, wheel: UvWheel, target_python: str, abi: str
    ) -> bool:
        """Check if a wheel is compatible with the target Python version.

        For abi3 wheels, the Python tag indicates minimum version (e.g., cp311-abi3 works with Python ≥3.11).
        For non-abi3 wheels, exact tag matching is required.
        """
        if target_python in wheel.python_tags:
            return True

        # For abi3 wheels, check if target >= minimum version (e.g., cp313 >= cp311)
        if abi == "abi3":
            return any(
                int(tag[2:]) <= int(target_python[2:])
                for tag in wheel.python_tags
                if tag.startswith("cp") and target_python.startswith("cp")
            )

        return False

    _manylinux_precedence: ClassVar[list[str]] = [
        "_2_28",  # glibc 2.28, latest stable version, supports Ubuntu 18.10+ and RHEL/Oracle 8+
        "_2_17",  # glibc 2.17, LTS-ish, supports Ubuntu 13.10+ and RHEL/Oracle 7+
        "2014",  # Synonym for _2_17
    ]
    platform_precedence_x86_64: ClassVar[list[str]] = [
        *[f"manylinux{version}_x86_64" for version in _manylinux_precedence],
        "any",
    ]
    platform_precedence_aarch64: ClassVar[list[str]] = [
        *[f"manylinux{version}_aarch64" for version in _manylinux_precedence],
        "any",
    ]

    build_from_source_warning_triggered: bool = False

    def _resolve(
        self, abi_precedence: list[str], python_precedence: list[str]
    ) -> DependencyWheel:
        """Resolve the dependency wheel for the given ABI and Python version."""
        wheel = DependencyWheel(
            module=self.name,
        )

        if (
            self.sdist is not None
            and normalize_package_name(self.name) in DEPENDENCIES_TO_BUILD
        ):
            wheel.sdist = self.sdist
            wheel.set_placeholder_wheel_name(self.version)

        if (
            self.source.directory is not None
            and normalize_package_name(self.name) in DEPENDENCIES_TO_BUILD
        ):
            wheel.source_dir = UvSourceDirectory(directory=self.source.directory)
            wheel.set_placeholder_wheel_name(self.version)

        try:
            wheel_x86_64 = self._find_wheel(
                abi_precedence, python_precedence, self.platform_precedence_x86_64
            )
            wheel.input_file = f"{wheel_x86_64.basename}.whl"
            wheel.wheel = wheel_x86_64
        except FileNotFoundError as e:
            if wheel.sdist is None and wheel.source_dir is None:
                raise FileNotFoundError(
                    f"Could not find a suitable x86_64 wheel or source distribution for {self.name}"
                ) from e
            elif not self.build_from_source_warning_triggered:
                logger.warning(
                    f"Dependency {self.name} will be built from source, as no wheel is available"
                )
                self.build_from_source_warning_triggered = True

        try:
            wheel_aarch64 = self._find_wheel(
                abi_precedence, python_precedence, self.platform_precedence_aarch64
            )
            wheel.input_file_aarch64 = f"{wheel_aarch64.basename}.whl"
            wheel.wheel_aarch64 = wheel_aarch64
        except FileNotFoundError:
            if wheel.sdist is None and wheel.source_dir is None:
                logger.warning(
                    f"Could not find a suitable aarch64 wheel for {self.name=}, {self.version=}, {abi_precedence=}, {python_precedence=} -- the built package might not work on ARM systems"
                )

        return wheel

    def resolve_py313(self) -> DependencyWheel:
        """Resolve the dependency wheel for Python 3.13."""
        return self._resolve(
            abi_precedence=[
                "cp313",  # Python 3.13-specific ABI
                "abi3",  # Python 3 stable ABI
                "none",  # Source wheels -- no ABI
            ],
            python_precedence=[
                "cp313",  # Binary wheel for Python 3.13
                "pp313",  # Source wheel for Python 3.13
                "py3",  # Source wheel for any Python 3.x
            ],
        )

    def resolve_py314(self) -> DependencyWheel:
        """Resolve the dependency wheel for Python 3.14."""
        return self._resolve(
            abi_precedence=[
                "cp314",  # Python 3.14-specific ABI
                "abi3",  # Python 3 stable ABI
                "none",  # Source wheels -- no ABI
            ],
            python_precedence=[
                "cp314",  # Binary wheel for Python 3.14
                "pp314",  # Source wheel for Python 3.14
                "py3",  # Source wheel for any Python 3.x
            ],
        )
