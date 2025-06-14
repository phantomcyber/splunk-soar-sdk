from enum import Enum
import functools
from packaging.version import Version

MIN_PHANTOM_VERSION = "6.4.0"


@functools.lru_cache(maxsize=32)
def remove_when_soar_newer_than(
    version: str, message: str = "", *, base_version: str = MIN_PHANTOM_VERSION
) -> None:
    if not message:
        message = "This code should be removed!"

    if Version(version) < Version(base_version):
        raise RuntimeError(f"Support for SOAR {version} is over. {message}")


class PythonVersion(str, Enum):
    """
    Enum to represent supported Python versions.
    """

    PY_3_9 = "3.9"
    PY_3_13 = "3.13"

    def __str__(self) -> str:
        """
        Returns the string representation of the Python version.
        """
        return self.value

    @classmethod
    def from_str(cls, version_str: str) -> "PythonVersion":
        """
        Returns the PythonVersion enum member corresponding to the given string.
        Raises ValueError if the version is not supported.
        """
        # "3" is a special case for connectors that don't properly define their Python version
        if version_str in ("3", "3.9"):
            return cls.PY_3_9
        if version_str == "3.13":
            return cls.PY_3_13

        raise ValueError(f"Unsupported Python version: {version_str}")

    @classmethod
    def from_csv(cls, version_csv: str) -> list["PythonVersion"]:
        """
        Parses a comma-separated string of Python versions and returns a list of PythonVersion enum members.
        Raises ValueError if any version is not supported.
        """
        versions = version_csv.split(",")
        return [
            cls.from_str(version.strip()) for version in versions if version.strip()
        ]

    @classmethod
    def all(cls) -> list["PythonVersion"]:
        """
        Returns a list of all supported Python versions.
        """
        return [cls.PY_3_9, cls.PY_3_13]

    @classmethod
    def to_requires_python(cls, versions: list["PythonVersion"]) -> str:
        """
        Converts a list of PythonVersion enum members to a PEP-508 compatible requires-python string.
        """
        versions = versions or cls.all()
        py_versions = sorted(Version(str(py)) for py in versions)
        next_version = f"{py_versions[-1].major}.{py_versions[-1].minor + 1}"

        return f">={py_versions[0]}, <{next_version}"
