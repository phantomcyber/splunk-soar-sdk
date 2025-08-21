try:
    from phantom.connector_result import ConnectorResult

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING


if TYPE_CHECKING or not _soar_is_available:
    import traceback

    class ConnectorResult:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.__exception_occured = False

        def add_exception(self, exception: Exception) -> bool:
            self.__exception_occured = True
            traceback.print_exception(
                type(exception), exception, exception.__traceback__
            )


__all__ = ["ConnectorResult"]
