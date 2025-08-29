import io
import os
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import build

from typing import Optional
from collections.abc import Mapping, Sequence, AsyncGenerator
from pydantic import BaseModel, Field

from logging import getLogger

import httpx
import hashlib

from soar_sdk.compat import remove_when_soar_newer_than


logger = getLogger(__name__)

# These dependencies are provided by the Python runner,
# so the SDK will not include wheels for them when building a package.
DEPENDENCIES_TO_SKIP = {
    # "splunk-soar-sdk",
    # List from https://docs.splunk.com/Documentation/SOAR/current/DevelopApps/FAQ
    "beautifulsoup4",
    "soupsieve",
    "parse",
    "python_dateutil",
    "six",
    "requests",
    "certifi",
    "charset_normalizer",
    "idna",
    "urllib3",
    "sh",
    "xmltodict",
}

# These dependencies should never be included with a connector,
# so the SDK will raise an error if it finds them in the lock.
DEPENDENCIES_TO_REJECT = {
    "simplejson",  # no longer needed, please use the built-in `json` module instead
    "django",  # apps should never depend on Django
}

# These dependencies can be built from a source distribution if no wheel is available.
# We should keep this list very short, pressure the maintainers of these packages to provide wheels,
# and remove packages from the list once they're available as wheels.
remove_when_soar_newer_than(
    "7.0.0",
    "If the Splunk SDK is available as a wheel now, remove it, and remove all of the code for building wheels from source.",
)
DEPENDENCIES_TO_BUILD = {
    "splunk_sdk",  # https://github.com/splunk/splunk-sdk-python/pull/656
}


class UvWheel(BaseModel):
    """Represents a Python wheel file with metadata and methods to fetch and validate it."""

    url: str
    hash: str
    size: Optional[int] = None

    # The wheel file name is specified by PEP427. It's either a 5- or 6-tuple:
    # {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    # We can parse this to determine which configurations it supports.
    @property
    def basename(self) -> str:
        """The base name of the wheel file."""
        remove_when_soar_newer_than(
            "6.4.0",
            "We should be able to adopt pydantic 2 now, and turn this into a cached property.",
        )
        filename = self.url.split("/")[-1]
        return filename.removesuffix(".whl")

    @property
    def distribution(self) -> str:
        """The distribution name (aka "package name") of the wheel."""
        return self.basename.split("-")[0]

    @property
    def version(self) -> str:
        """The version number of the wheel."""
        return self.basename.split("-")[1]

    @property
    def build_tag(self) -> Optional[str]:
        """An optional build tag for the wheel."""
        split = self.basename.split("-")
        if len(split) == 6:
            return split[2]
        return None

    @property
    def python_tags(self) -> list[str]:
        """The Python version tags (cp39, pp313, etc.) for the wheel."""
        return self.basename.split("-")[-3].split(".")

    @property
    def abi_tags(self) -> list[str]:
        """The ABI tags (none, cp39, etc.) for the wheel."""
        return self.basename.split("-")[-2].split(".")

    @property
    def platform_tags(self) -> list[str]:
        """The platform tags (manylinux_2_28_x86_64, any, etc.) for the wheel."""
        return self.basename.split("-")[-1].split(".")

    def validate_hash(self, wheel: bytes) -> None:
        """Validate the hash of the downloaded wheel against the expected hash."""
        algorithm, expected_digest = self.hash.split(":")
        actual_digest = hashlib.new(algorithm, wheel).hexdigest()
        if expected_digest != actual_digest:
            raise ValueError(
                f"Retrieved wheel for {self.distribution}-{self.version} did not match the expected checksum. {expected_digest=}, {actual_digest=}, {self.url=}"
            )

    async def fetch(self) -> bytes:
        """Download the wheel file from the specified URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url, timeout=10)
            response.raise_for_status()
            wheel_bytes: bytes = response.content
            self.validate_hash(wheel_bytes)
            return wheel_bytes


class UvSourceDistribution(BaseModel):
    """Represents a source distribution (sdist) for a Python package."""

    url: str
    hash: str
    size: Optional[int] = None

    def validate_hash(self, sdist: bytes) -> None:
        """Validate the hash of the downloaded sdist against the expected hash."""
        algorithm, expected_digest = self.hash.split(":")
        actual_digest = hashlib.new(algorithm, sdist).hexdigest()
        if expected_digest != actual_digest:
            raise ValueError(
                f"Retrieved sdist for {self.url} did not match the expected checksum. {expected_digest=}, {actual_digest=}, {self.url=}"
            )

    async def fetch_and_build(self) -> tuple[str, bytes]:
        """Download the source distribution and build a wheel from it."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url, timeout=10)
            response.raise_for_status()
            sdist_bytes: bytes = response.content
            self.validate_hash(sdist_bytes)
            return self._build_wheel(sdist_bytes)

    @staticmethod
    def _builder_runner(
        cmd: Sequence[str],
        cwd: Optional[str] = None,
        extra_environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Run a command in a subprocess and return its exit code, stdout, and stderr."""
        proc = subprocess.run(  # noqa: S603
            cmd, cwd=cwd, env=extra_environ, text=True, check=True, capture_output=True
        )
        for line in proc.stdout.splitlines():
            logger.debug(f"Builder stdout: {line}")
        for line in proc.stderr.splitlines():
            logger.debug(f"Builder stderr: {line}")

    def _build_wheel(self, sdist: bytes) -> tuple[str, bytes]:
        """Build a wheel from the downloaded source distribution."""
        with (
            TemporaryDirectory() as extract_dir,
            tarfile.open(fileobj=io.BytesIO(sdist), mode="r") as tar,
            TemporaryDirectory() as build_dir,
        ):
            top_level_dir = os.path.commonprefix(tar.getnames())
            tar.extractall(path=extract_dir, filter="data")
            sdist_path = f"{extract_dir}/{top_level_dir}"
            builder = build.ProjectBuilder(sdist_path, runner=self._builder_runner)
            wheel_path = builder.build("wheel", build_dir)
            with open(wheel_path, "rb") as f:
                return Path(wheel_path).name, f.read()


class DependencyWheel(BaseModel):
    """Represents a Python package dependency with all the information required to fetch its wheel(s) from the CDN."""

    module: str
    input_file: str = ""
    input_file_aarch64: Optional[str] = None

    wheel: Optional[UvWheel] = Field(exclude=True, default=None)
    wheel_aarch64: Optional[UvWheel] = Field(exclude=True, default=None)
    sdist: Optional[UvSourceDistribution] = Field(exclude=True, default=None)

    async def collect_wheels(self) -> AsyncGenerator[tuple[str, bytes], None]:
        """Collect a list of wheel files to fetch for this dependency across all platforms."""
        if self.wheel is None and self.sdist is not None:
            logger.info(f"Building sdist for {self.input_file}")
            wheel_name, wheel_bytes = await self.sdist.fetch_and_build()
            yield (f"wheels/shared/{wheel_name}", wheel_bytes)
            return

        if self.wheel is None:
            raise ValueError(
                f"Could not find a suitable wheel or source distribution for {self.module} in uv.lock"
            )

        wheel_bytes = await self.wheel.fetch()
        yield (self.input_file, wheel_bytes)

        if (
            self.input_file_aarch64 is not None
            and self.wheel_aarch64 is not None
            and self.input_file_aarch64 != self.input_file
        ):
            wheel_aarch64_bytes = await self.wheel_aarch64.fetch()
            yield (self.input_file_aarch64, wheel_aarch64_bytes)

    def add_platform_prefix(self, prefix: str) -> None:
        """Add a platform prefix to the input file paths."""
        self.input_file = f"wheels/{prefix}/{self.input_file}"
        if self.input_file_aarch64:
            self.input_file_aarch64 = f"wheels/{prefix}/{self.input_file_aarch64}"

    def __hash__(self) -> int:
        """Compute a hash for the dependency wheel so we can dedupe wheel files in a later step."""
        return hash((type(self), *tuple(self.dict().items())))


class DependencyList(BaseModel):
    """Represents a list of Python package dependencies for the app."""

    wheel: list[DependencyWheel] = Field(default_factory=list)


class UvDependency(BaseModel):
    """Represents a Python dependency relationship loaded from the uv lock."""

    name: str


class UvPackage(BaseModel):
    """Represents a Python package loaded from the uv lock."""

    name: str
    version: str
    dependencies: list[UvDependency] = []
    optional_dependencies: dict[str, list[UvDependency]] = Field(
        default_factory=dict, alias="optional-dependencies"
    )
    wheels: list[UvWheel] = []
    sdist: Optional[UvSourceDistribution] = None

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
                python_wheels = [
                    wheel for wheel in abi_wheels if python in wheel.python_tags
                ]
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

    _manylinux_precedence = [
        "_2_28",  # glibc 2.28, latest stable version, supports Ubuntu 18.10+ and RHEL/Oracle 8+
        "_2_17",  # glibc 2.17, LTS-ish, supports Ubuntu 13.10+ and RHEL/Oracle 7+
        "2014",  # Synonym for _2_17
    ]
    platform_precedence_x86_64 = [
        *[f"manylinux{version}_x86_64" for version in _manylinux_precedence],
        "any",
    ]
    platform_precedence_aarch64 = [
        *[f"manylinux{version}_aarch64" for version in _manylinux_precedence],
        "any",
    ]

    build_from_source_warning_triggered = False

    def _resolve(
        self, abi_precedence: list[str], python_precedence: list[str]
    ) -> DependencyWheel:
        """Resolve the dependency wheel for the given ABI and Python version."""
        wheel = DependencyWheel(
            module=self.name,
        )

        if (
            self.sdist is not None
            and UvLock.normalize_package_name(self.name) in DEPENDENCIES_TO_BUILD
        ):
            wheel.sdist = self.sdist

        try:
            wheel_x86_64 = self._find_wheel(
                abi_precedence, python_precedence, self.platform_precedence_x86_64
            )
            wheel.input_file = f"{wheel_x86_64.basename}.whl"
            wheel.wheel = wheel_x86_64
        except FileNotFoundError as e:
            if wheel.sdist is None:
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
            if wheel.sdist is None:
                logger.warning(
                    f"Could not find a suitable aarch64 wheel for {self.name=}, {self.version=}, {abi_precedence=}, {python_precedence=} -- the built package might not work on ARM systems"
                )

        return wheel

    def resolve_py39(self) -> DependencyWheel:
        """Resolve the dependency wheel for Python 3.9."""
        return self._resolve(
            abi_precedence=[
                "cp39",  # Python 3.9-specific ABI
                "abi3",  # Python 3 stable ABI
                "none",  # Source wheels -- no ABI
            ],
            python_precedence=[
                "cp39",  # Binary wheel for Python 3.9
                "pp39",  # Source wheel for Python 3.9
                "py3",  # Source wheel for any Python 3.x
            ],
        )

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


class UvLock(BaseModel):
    """Represents the structure of the uv lock file."""

    package: list[UvPackage]

    @staticmethod
    def normalize_package_name(name: str) -> str:
        """Normalize the package name by converting it to lowercase and replacing hyphens with underscores.

        Python treats package names as case-insensitive and doesn't differentiate between hyphens and
        underscores, so "my_awesome_package" is equivalent to "mY_aWeSoMe-pAcKaGe".
        """
        return name.lower().replace("-", "_")

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
    ) -> tuple[DependencyList, DependencyList]:
        """Resolve the dependencies for the given packages."""
        py39_wheels: list[DependencyWheel] = []
        py313_wheels: list[DependencyWheel] = []

        for package in packages:
            wheel_39 = package.resolve_py39()
            wheel_313 = package.resolve_py313()

            if wheel_39 == wheel_313:
                wheel_39.add_platform_prefix("shared")
                wheel_313.add_platform_prefix("shared")
            else:
                wheel_39.add_platform_prefix("python39")
                wheel_313.add_platform_prefix("python313")

            py39_wheels.append(wheel_39)
            py313_wheels.append(wheel_313)

        return DependencyList(wheel=py39_wheels), DependencyList(wheel=py313_wheels)
