from soar_sdk.compat import remove_when_soar_newer_than

try:
    import ph_ipc

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING, overload

if TYPE_CHECKING or not _soar_is_available:

    class _PhIPCShim:
        PH_STATUS_PROGRESS = 1

        remove_when_soar_newer_than(
            "7.0.0",
            'The "Old SOAR" variants of the ph_ipc methods are no longer used.',
        )

        @overload
        @staticmethod
        def sendstatus(status: int, message: str, flag: bool) -> None: ...
        @overload
        @staticmethod
        def sendstatus(
            handle: int | None, status: int, message: str, flag: bool
        ) -> None: ...
        @staticmethod
        def sendstatus(*args: object) -> None:
            # New SOAR (3 args): status, message, flag
            # Old SOAR (4 args): handle, status, message, flag
            message = args[1] if len(args) == 3 else args[2]
            print(message)

        @overload
        @staticmethod
        def debugprint(message: str) -> None: ...
        @overload
        @staticmethod
        def debugprint(handle: int | None, message: str, level: int) -> None: ...
        @staticmethod
        def debugprint(*args: object) -> None:
            # New SOAR (1 arg): message
            # Old SOAR (3 args): handle, message, level
            message = args[0] if len(args) == 1 else args[1]
            print(message)

        @overload
        @staticmethod
        def errorprint(message: str) -> None: ...
        @overload
        @staticmethod
        def errorprint(handle: int | None, message: str, level: int) -> None: ...
        @staticmethod
        def errorprint(*args: object) -> None:
            # New SOAR (1 arg): message
            # Old SOAR (3 args): handle, message, level
            message = args[0] if len(args) == 1 else args[1]
            print(message)

    ph_ipc = _PhIPCShim()

__all__ = ["ph_ipc"]
