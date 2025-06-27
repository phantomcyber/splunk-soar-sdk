try:
    import ph_ipc  # type: ignore[import-not-found]

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING or not _soar_is_available:
    from soar_sdk.shims.phantom.install_info import get_product_version
    from packaging.version import Version

    if Version(get_product_version()) >= Version("7.0.0"):

        class _PhIPCShim:
            PH_STATUS_PROGRESS = 1

            @staticmethod
            def sendstatus(status: int, message: str, flag: bool) -> None:
                print(message)

            @staticmethod
            def debugprint(message: str) -> None:
                print(message)

            @staticmethod
            def errorprint(message: str) -> None:
                print(message)
    else:

        class _PhIPCShim:  # type: ignore[no-redef]
            PH_STATUS_PROGRESS = 1

            @staticmethod
            def sendstatus(
                handle: Optional[int], status: int, message: str, flag: bool
            ) -> None:
                print(message)

            @staticmethod
            def debugprint(handle: Optional[int], message: str, level: int) -> None:
                print(message)

            @staticmethod
            def errorprint(message: str) -> None:
                print(message)

    ph_ipc = _PhIPCShim()

__all__ = ["ph_ipc"]
