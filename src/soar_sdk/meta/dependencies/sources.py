import functools
import hashlib
import io
import os
import subprocess
import tarfile
from collections.abc import Mapping, Sequence
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory

import build
import httpx
from pydantic import BaseModel

logger = getLogger("soar_sdk.meta.dependencies")


class UvWheel(BaseModel):
    """Represents a Python wheel file with metadata and methods to fetch and validate it."""

    url: str | None = None
    filename: str | None = None
    hash: str
    size: int | None = None

    # The wheel file name is specified by PEP427. It's either a 5- or 6-tuple:
    # {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    # We can parse this to determine which configurations it supports.
    @functools.cached_property
    def basename(self) -> str:
        """The base name of the wheel file."""
        if self.filename:
            return self.filename.removesuffix(".whl")
        if self.url:
            filename = self.url.split("/")[-1]
            return filename.removesuffix(".whl")
        raise ValueError("UvWheel must have either url or filename")

    @property
    def distribution(self) -> str:
        """The distribution name (aka "package name") of the wheel."""
        return self.basename.split("-")[0]

    @property
    def version(self) -> str:
        """The version number of the wheel."""
        return self.basename.split("-")[1]

    @property
    def build_tag(self) -> str | None:
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
        if self.url is None:
            raise ValueError(
                f"Cannot fetch wheel {self.filename or 'unknown'}: no URL provided (local file reference?)"
            )
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
    size: int | None = None

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
        cwd: str | None = None,
        extra_environ: Mapping[str, str] | None = None,
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


class UvSourceDirectory(BaseModel):
    """Represents a Python dependency to be built from a source directory on the local filesystem."""

    directory: str

    def build(self) -> tuple[str, bytes]:
        """Build a wheel from a local source directory."""
        with TemporaryDirectory() as build_dir:
            builder = build.ProjectBuilder(
                self.directory,
                runner=UvSourceDistribution._builder_runner,
            )
            wheel_path = builder.build("wheel", build_dir)
            with open(wheel_path, "rb") as f:
                return Path(wheel_path).name, f.read()
