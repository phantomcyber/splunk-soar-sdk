from collections.abc import AsyncGenerator
from logging import getLogger
from pathlib import Path

from pydantic import BaseModel, Field

from .sources import UvSourceDirectory, UvSourceDistribution, UvWheel

logger = getLogger("soar_sdk.meta.dependencies")


class DependencyWheel(BaseModel):
    """Represents a Python package dependency with all the information required to fetch its wheel(s) from the CDN."""

    module: str
    input_file: str = ""
    input_file_aarch64: str | None = None

    wheel: UvWheel | None = Field(exclude=True, default=None)
    wheel_aarch64: UvWheel | None = Field(exclude=True, default=None)
    sdist: UvSourceDistribution | None = Field(exclude=True, default=None)
    source_dir: UvSourceDirectory | None = Field(exclude=True, default=None)

    def _set_wheel_paths(self, wheel_name: str) -> str:
        """Assign the final wheel path (with any existing prefix) to both arches."""
        base_path = Path(self.input_file or "wheels/shared")
        # If there's already a filename component, replace it instead of nesting it
        if base_path.suffix == ".whl":
            base_path = base_path.parent
        wheel_path = (base_path / wheel_name).as_posix()
        self.input_file = wheel_path
        self.input_file_aarch64 = wheel_path
        return wheel_path

    def set_placeholder_wheel_name(self, version: str) -> None:
        """Populate a clearly placeholder wheel path when we expect to build from source."""
        # Use only a filename here; platform-specific prefixes are added later.
        self.input_file = "<to_be_built>.whl"
        self.input_file_aarch64 = "<to_be_built>.whl"

    def _record_built_wheel(self, wheel_name: str) -> str:
        """Fill in missing wheel paths once a wheel has been built from source."""
        return self._set_wheel_paths(wheel_name)

    async def collect_wheels(self) -> AsyncGenerator[tuple[str, bytes]]:
        """Collect a list of wheel files to fetch for this dependency across all platforms."""
        if self.wheel is None and self.sdist is not None:
            logger.info(f"Building sdist for {self.input_file}")
            wheel_name, wheel_bytes = await self.sdist.fetch_and_build()
            wheel_path = self._record_built_wheel(wheel_name)
            yield (wheel_path, wheel_bytes)
            return

        if self.wheel is None and self.source_dir is not None:
            logger.info(f"Building local sources for {self.input_file}")
            wheel_name, wheel_bytes = self.source_dir.build()
            wheel_path = self._record_built_wheel(wheel_name)
            yield (wheel_path, wheel_bytes)
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
        return hash((type(self), *tuple(self.model_dump().items())))


class DependencyList(BaseModel):
    """Represents a list of Python package dependencies for the app."""

    wheel: list[DependencyWheel] = Field(default_factory=list)
