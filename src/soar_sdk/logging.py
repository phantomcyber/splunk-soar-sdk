import logging
from soar_sdk.colors import ANSIColor

from soar_sdk.connector import AppConnector
from soar_sdk.shims.phantom.install_info import is_soar_available

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

    def emit(self, record: logging.LogRecord) -> None:
        soar_client = AppConnector.get_instance()
        if not soar_client:
            # This should never happen, but added to pass mypy
            raise RuntimeError("SOAR client is not initialized")
        try:
            message = self.format(record)
            if record.levelno == PROGRESS_LEVEL:
                soar_client.send_progress(message)
            elif record.levelno in (logging.DEBUG, logging.WARNING, logging.ERROR):
                soar_client.debug(message)
            elif record.levelno == logging.CRITICAL:
                soar_client.error(message)
            elif record.levelno == logging.INFO:
                soar_client.save_progress(message)
            else:
                raise ValueError("Log level not supporeted")
        except Exception:
            self.handleError(record)


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
                kwargs.pop("exc_info", None),  # type: ignore
                kwargs,
            )

    def removeHandler(self, handler: logging.Handler) -> None:
        """
        Remove a handler from the logger.
        """
        if isinstance(handler, SOARHandler):
            raise ValueError("Removing the SOARHandler is not allowed.")
        super().removeHandler(handler)


def getLogger(name: str = "phantom_logger") -> PhantomLogger:
    """
    Get a logger instance with the custom SOAR handler.
    """
    return PhantomLogger(name=name)
