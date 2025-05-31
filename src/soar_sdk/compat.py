from enum import Enum

MIN_PHANTOM_VERSION = "6.4.0"


class PythonVersion(str, Enum):
    """
    Enum to represent supported Python versions.
    """

    PY_3_9 = "3.9"
    PY_3_13 = "3.13"

    @classmethod
    def all(cls) -> list["PythonVersion"]:
        """
        Returns a list of all supported Python versions.
        """
        return [cls.PY_3_9, cls.PY_3_13]
