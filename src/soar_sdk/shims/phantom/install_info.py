try:
    from phantom_common.install_info import get_verify_ssl_setting

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:

    def get_verify_ssl_setting() -> bool:
        """Mock function to simulate the behavior of get_verify_ssl_setting."""
        return False


def is_soar_available() -> bool:
    """
    Returns whether SOAR is available.
    """
    return _soar_is_available


__all__ = ["get_verify_ssl_setting", "is_soar_available"]
