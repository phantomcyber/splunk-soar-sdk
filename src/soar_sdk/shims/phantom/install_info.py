try:
    from phantom_common.install_info import (
        get_product_version,
        get_verify_ssl_setting,
        is_onprem_broker_install,
    )

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:

    def get_verify_ssl_setting() -> bool:
        """Mock function to simulate the behavior of get_verify_ssl_setting."""
        return False

    def get_product_version() -> str:
        """Mock function to simulate the behavior of get_product_version."""
        return "6.4.1"

    def is_onprem_broker_install() -> bool:
        """Mock function to simulate the behavior of is_onprem_broker_install."""
        return False


def is_soar_available() -> bool:
    """
    Returns whether SOAR is available.
    """
    return _soar_is_available


__all__ = [
    "get_product_version",
    "get_verify_ssl_setting",
    "is_onprem_broker_install",
    "is_soar_available",
]
