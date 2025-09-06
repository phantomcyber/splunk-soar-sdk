import logging
from soar_sdk.colors import ANSIColor

from soar_sdk.shims.phantom.install_info import is_soar_available, get_product_version
from soar_sdk.shims.phantom.ph_ipc import ph_ipc
from packaging.version import Version
from typing import Any, Optional
from soar_sdk.compat import remove_when_soar_newer_than

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
    """Custom logging handler to send logs to the SOAR client."""

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.__handle: Optional[int] = None

    def emit(self, record: logging.LogRecord) -> None:
        is_new_soar = Version(get_product_version()) >= Version("7.0.0")
        remove_when_soar_newer_than(
            "7.0.0",
            "In 7.0.0+ ph_ipc is injected into the module path by spawn so passing handle is not needed",
        )

        try:
            message = self.format(record)
            if record.levelno == PROGRESS_LEVEL:
                if is_new_soar:
                    ph_ipc.sendstatus(ph_ipc.PH_STATUS_PROGRESS, message, False)
                else:
                    ph_ipc.sendstatus(
                        self.__handle, ph_ipc.PH_STATUS_PROGRESS, message, False
                    )
            elif record.levelno in (logging.DEBUG, logging.WARNING):
                if is_new_soar:
                    ph_ipc.debugprint(message)
                else:
                    ph_ipc.debugprint(self.__handle, message, 2)
            elif record.levelno in (logging.ERROR, logging.CRITICAL):
                if is_new_soar:
                    ph_ipc.errorprint(message)
                else:
                    ph_ipc.errorprint(self.__handle, message, 2)
            elif record.levelno == logging.INFO:
                if is_new_soar:
                    ph_ipc.sendstatus(ph_ipc.PH_STATUS_PROGRESS, message, True)
                else:
                    ph_ipc.sendstatus(
                        self.__handle, ph_ipc.PH_STATUS_PROGRESS, message, True
                    )

            else:
                raise ValueError("Log level not supporeted")
        except Exception:
            self.handleError(record)

    def set_handle(self, handle: Optional[int]) -> None:
        """Set the action handle for the SOAR client."""
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
        """Log a message with the PROGRESS level."""
        if self.isEnabledFor(PROGRESS_LEVEL):
            self._log(
                PROGRESS_LEVEL,
                message,
                args,
                **kwargs,  # type: ignore
            )

    def removeHandler(self, hdlr: logging.Handler) -> None:
        """Remove a handler from the logger."""
        if isinstance(hdlr, SOARHandler):
            raise ValueError("Removing the SOARHandler is not allowed.")
        super().removeHandler(hdlr)


# Expose logging methods as top-level functions
def debug(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log a debug message using the default SOAR logger.

    Convenience function for debug-level logging without needing to instantiate
    a logger. This function uses the singleton SOAR logger instance and supports
    all standard Python logging formatting and options.

    Args:
        msg (str): The log message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import debug
        >>> debug("Processing user: %s", username)
    """
    getLogger().debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log an informational message using the default SOAR logger.

    Convenience function for info-level logging without needing to instantiate
    a logger. Use this for general informational messages about normal program
    execution and important events.

    Args:
        msg (str): The log message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import info
        >>> info("Action started successfully")
    """
    getLogger().info(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log a warning message using the default SOAR logger.

    Convenience function for warning-level logging without needing to instantiate
    a logger. Use this for potentially harmful situations that don't prevent the
    program from continuing but warrant attention.

    Args:
        msg (str): The log message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import warning
        >>> warning("API rate limit approaching")
    """
    getLogger().warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log an error message using the default SOAR logger.

    Convenience function for error-level logging without needing to instantiate
    a logger. Use this for error conditions that are serious but allow the
    program to continue running.

    Args:
        msg (str): The log message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import error
        >>> error("Failed to connect to external API")
    """
    getLogger().error(msg, *args, **kwargs)


def critical(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log a critical error message using the default SOAR logger.

    Convenience function for critical-level logging without needing to instantiate
    a logger. Use this for very serious error events that may cause the program
    to abort or require immediate attention.

    Args:
        msg (str): The log message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import critical
        >>> critical("Database connection lost, cannot continue")
    """
    getLogger().critical(msg, *args, **kwargs)


def progress(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Log a progress message using the default SOAR logger.

    Convenience function for progress-level logging without needing to instantiate
    a logger. This is a custom logging level specific to SOAR that's used to
    report action progress and status updates to users. Progress messages are
    typically displayed in the SOAR UI to show action execution status.

    Args:
        msg (str): The progress message. Supports Python string formatting with
                  positional arguments.
        *args: Variable length argument list for string formatting.
        **kwargs: Arbitrary keyword arguments passed to the underlying logger.

    Example:
        >>> from soar_sdk.logging import progress
        >>> progress("Starting data collection...")

    Note:
        Progress messages are displayed to end users in the SOAR interface,
        so they should be clear, informative, and user-friendly.
    """
    getLogger().progress(msg, *args, **kwargs)


def getLogger(name: str = "phantom_logger") -> PhantomLogger:
    """Get the recommended logger for SOAR SDK applications.

    This is the standard logger you should use in all SOAR applications built
    with the SDK. It provides all normal Python logging capabilities with
    additional SOAR-specific features like progress logging and integration
    with the SOAR platform's logging system.

    The logger supports all standard Python logging levels (DEBUG, INFO, WARNING,
    ERROR, CRITICAL) plus a custom PROGRESS level for tracking action progress.

    Args:
        name (str, optional): The name for the logger instance. Defaults to
                            "phantom_logger" for compatibility.

    Returns:
        PhantomLogger: A logger instance with SOAR-specific capabilities that
                      extends the standard Python logger interface.

    Example:
        >>> from soar_sdk.logging import getLogger
        >>> logger = getLogger()
        >>> logger.debug("Debug message for troubleshooting")
        >>> logger.info("Informational message")
        >>> logger.warning("Warning about potential issue")
        >>> logger.error("Error occurred during processing")
        >>> logger.progress("Action is 50% complete")
        >>>
        >>> # Logger supports all standard logging methods
        >>> logger.setLevel(logging.DEBUG)
        >>> logger.addHandler(custom_handler)
        >>> logger.log(logging.INFO, "Custom level logging")

    Note:
        This function returns a singleton instance, so multiple calls with the
        same name will return the same logger object for consistency across
        your application.
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
