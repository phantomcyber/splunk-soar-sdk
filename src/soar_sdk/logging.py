import logging
from soar_sdk.colors import ANSIColor

from soar_sdk.shims.phantom.install_info import is_soar_available
from soar_sdk.shims.phantom.ph_ipc import ph_ipc
from typing import Any, Optional

PROGRESS_LEVEL = 25
logging.addLevelName(PROGRESS_LEVEL, "PROGRESS")


class ColorFilter(logging.Filter):
    def __init__(self, *args: object, color: bool = True, **kwargs: object) -> None:
        super().__init__()
        self.ansi_colors = ANSIColor(color)

        self.level_colors = {
            logging.DEBUG: self.ansi_colors.DIM,
            logging.INFO: self.ansi_colors.RESET,
            logging.WARNING: self.ansi_colors.YELLOW,
            logging.ERROR: self.ansi_colors.BOLD_RED,
            logging.CRITICAL: self.ansi_colors.BOLD_UNDERLINE_RED,
            logging.NOTSET: self.ansi_colors.BOLD_UNDERLINE_RED,
        }

    def filter(self, record: logging.LogRecord) -> bool:
        record.color = self.level_colors.get(record.levelno, "")
        record.reset = self.ansi_colors.RESET
        return True


class SOARHandler(logging.Handler):
    """
    Custom logging handler to send logs to the SOAR client.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.__handle: Optional[int] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            if record.levelno == PROGRESS_LEVEL:
                ph_ipc.sendstatus(
                    self.__handle, ph_ipc.PH_STATUS_PROGRESS, message, False
                )
            elif record.levelno in (logging.DEBUG, logging.WARNING, logging.ERROR):
                ph_ipc.debugprint(self.__handle, message, 2)
            elif record.levelno == logging.CRITICAL:
                ph_ipc.errorprint(self.__handle, message, 2)
            elif record.levelno == logging.INFO:
                ph_ipc.sendstatus(
                    self.__handle, ph_ipc.PH_STATUS_PROGRESS, message, True
                )
            else:
                raise ValueError("Log level not supporeted")
        except Exception:
            self.handleError(record)

    def set_handle(self, handle: Optional[int]) -> None:
        """
        Set the action handle for the SOAR client.
        """
        self.__handle = handle


class PhantomLogger(logging.Logger):
    _instance = None

    def __new__(cls, name: str = "phantom_logger") -> "PhantomLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.name = name  # Set the name for the first time
        return cls._instance

    def __init__(self, name: str = "phantom_logger") -> None:
        super().__init__(name)
        self.setLevel(logging.DEBUG)
        self.handler = SOARHandler()
        self.handler.addFilter(ColorFilter(color=not is_soar_available()))
        console_format = "{color}{message}{reset}"
        console_formatter = logging.Formatter(fmt=console_format, style="{")
        self.handler.setFormatter(console_formatter)
        self.addHandler(self.handler)

    def progress(self, message: str, *args: object, **kwargs: object) -> None:
        """
        Log a message with the PROGRESS level.
        """
        if self.isEnabledFor(PROGRESS_LEVEL):
            self._log(
                PROGRESS_LEVEL,
                message,
                args,
                **kwargs,  # type: ignore
            )

    def removeHandler(self, hdlr: logging.Handler) -> None:
        """
        Remove a handler from the logger.
        """
        if isinstance(hdlr, SOARHandler):
            raise ValueError("Removing the SOARHandler is not allowed.")
        super().removeHandler(hdlr)


# Expose logging methods as top-level functions
def debug(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().info(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().error(msg, *args, **kwargs)


def critical(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().critical(msg, *args, **kwargs)


def progress(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    getLogger().progress(msg, *args, **kwargs)


def getLogger(name: str = "phantom_logger") -> PhantomLogger:
    """
    Get a logger instance with the custom SOAR handler.
    """

    if PhantomLogger._instance is None:
        return PhantomLogger(name)
    return PhantomLogger._instance


__all__ = [
    "critical",
    "debug",
    "error",
    "getLogger",
    "info",
    "progress",
    "warning",
]
