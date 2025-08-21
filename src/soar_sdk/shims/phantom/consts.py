try:
    from phantom import consts

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:

    class Consts:
        APP_DEFAULT_ARTIFACT_LABEL = "artifact"
        APP_DEFAULT_CONTAINER_LABEL = "incident"
        APP_DEFAULT_ARTIFACT_TYPE = "network"

    consts = Consts()

__all__ = ["consts"]
