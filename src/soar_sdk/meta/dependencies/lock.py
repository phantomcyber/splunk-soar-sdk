from logging import getLogger

from pydantic import BaseModel

from .constants import DEPENDENCIES_TO_REJECT, DEPENDENCIES_TO_SKIP
from .package import UvPackage
from .utils import normalize_package_name as _normalize_package_name
from .wheels import DependencyList

logger = getLogger("soar_sdk.meta.dependencies")


class UvLock(BaseModel):
    """Represents the structure of the uv lock file."""

    package: list[UvPackage]

    @staticmethod
    def normalize_package_name(name: str) -> str:
        """Normalize the package name by converting it to lowercase and replacing hyphens with underscores.

        Python treats package names as case-insensitive and doesn't differentiate between hyphens and
        underscores, so "my_awesome_package" is equivalent to "mY_aWeSoMe-pAcKaGe".
        """
        return _normalize_package_name(name)

    def get_package_entry(self, name: str) -> UvPackage:
        """Find the lock entry for a given package name (ignoring differences in case and punctuation)."""
        name = self.normalize_package_name(name)
        package = next(
            (p for p in self.package if self.normalize_package_name(p.name) == name),
            None,
        )
        if package is None:
            raise LookupError(f"No package '{name}' found in uv.lock")
        return package

    def build_package_list(self, root_package_name: str) -> list[UvPackage]:
        """Build a list of all packages required by the root package."""
        packages = {root_package_name: self.get_package_entry(root_package_name)}

        new_packages_added = True
        while new_packages_added:
            new_packages_added = False

            scan_pass = list(packages.values())
            for package in scan_pass:
                package_dependencies = package.dependencies

                for extra_group in package.optional_dependencies.values():
                    package_dependencies += extra_group

                for dependency in package_dependencies:
                    name = dependency.name

                    if name in DEPENDENCIES_TO_REJECT:
                        raise ValueError(
                            f"The '{name}' package is not allowed in a SOAR connector. Please remove it from your app's dependencies."
                        ) from None
                    if name in DEPENDENCIES_TO_SKIP:
                        logger.info(
                            f"Not bundling wheel for '{name}' because it is included with the SOAR platform."
                        )
                        continue

                    if name not in packages:
                        packages[name] = self.get_package_entry(name)
                        new_packages_added = True

        # Exclude the connector itself from the list of dependencies
        del packages[root_package_name]

        return sorted(packages.values(), key=lambda p: p.name)

    @staticmethod
    def resolve_dependencies(
        packages: list[UvPackage],
        python_versions: list[str] | None = None,
    ) -> tuple[DependencyList, DependencyList]:
        """Resolve the dependencies for the given packages.

        Args:
            packages: List of packages to resolve dependencies for.
            python_versions: List of Python versions to resolve for (e.g., ["3.13", "3.14"]).
                           If None, defaults to ["3.13", "3.14"] for backwards compatibility.

        Returns:
            Tuple of (py313_dependencies, py314_dependencies).
        """
        python_versions = python_versions or ["3.13", "3.14"]
        resolve_both = len(python_versions) == 2

        py313_wheels, py314_wheels = [], []

        for package in packages:
            wheel_313 = package.resolve_py313() if "3.13" in python_versions else None
            wheel_314 = package.resolve_py314() if "3.14" in python_versions else None

            prefix = "shared" if not resolve_both or wheel_313 == wheel_314 else None

            if wheel_313:
                wheel_313.add_platform_prefix(prefix or "python313")
                py313_wheels.append(wheel_313)

            if wheel_314:
                wheel_314.add_platform_prefix(prefix or "python314")
                py314_wheels.append(wheel_314)

        return DependencyList(wheel=py313_wheels), DependencyList(wheel=py314_wheels)
