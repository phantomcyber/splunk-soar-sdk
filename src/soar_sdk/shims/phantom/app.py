try:
    from phantom.app import APP_SUCCESS, APP_ERROR

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    APP_SUCCESS = True
    APP_ERROR = False


__all__ = ["APP_ERROR", "APP_SUCCESS"]
