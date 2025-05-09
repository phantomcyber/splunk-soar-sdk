try:
    import ph_ipc  # type: ignore[import-not-found]

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING or not _soar_is_available:

    class _PhIPCShim:
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
        def errorprint(handle: Optional[int], message: str, level: int) -> None:
            print(message)

    ph_ipc = _PhIPCShim()

__all__ = ["ph_ipc"]
