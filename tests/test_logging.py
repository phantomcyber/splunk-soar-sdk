from unittest import mock
import pytest

from soar_sdk.connector import AppConnector
from soar_sdk.logging import (
    getLogger,
    debug,
    error,
    info,
    progress,
    critical,
    warning,
    SOARHandler,
    PhantomLogger,
)
from soar_sdk.colors import ANSIColor
import soar_sdk.logging
from soar_sdk.shims.phantom.ph_ipc import ph_ipc

ph_ipc.sendstatus = mock.Mock()
ph_ipc.debugprint = mock.Mock()
ph_ipc.errorprint = mock.Mock()


def test_root_logger():
    import logging as python_logger

    logger = python_logger.getLogger()
    logger.warning("This is an info message from the test_logging module.")
    ph_ipc.debugprint.assert_called_once()


def test_logging():
    logger = getLogger()

    logger.info("This is an info message from the test_logging module.")
    ph_ipc.sendstatus.assert_called_with(
        None,
        1,
        "\x1b[0mThis is an info message from the test_logging module.\x1b[0m",
        True,
    )

    logger.debug("This is a debug message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None, "\x1b[2mThis is a debug message from the test_logging module.\x1b[0m", 2
    )

    logger.critical("This is a critical message from the test_logging module.")
    ph_ipc.errorprint.assert_called_with(
        None,
        "\x1b[1;4;31mThis is a critical message from the test_logging module.\x1b[0m",
        2,
    )

    logger.progress("This is a progress message from the test_logging module.")
    ph_ipc.sendstatus.assert_called_with(
        None,
        1,
        "This is a progress message from the test_logging module.\x1b[0m",
        False,
    )

    logger.warning("This is a warning message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None,
        "\x1b[33mThis is a warning message from the test_logging module.\x1b[0m",
        2,
    )

    logger.error("This is a warning message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None,
        "\x1b[1;31mThis is a warning message from the test_logging module.\x1b[0m",
        2,
    )


def test_standalone_logging(app_connector: AppConnector):
    info("This is an info message from the test_logging module.")
    ph_ipc.sendstatus.assert_called_with(
        None,
        1,
        "\x1b[0mThis is an info message from the test_logging module.\x1b[0m",
        True,
    )

    debug("This is a debug message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None, "\x1b[2mThis is a debug message from the test_logging module.\x1b[0m", 2
    )

    critical("This is a critical message from the test_logging module.")
    ph_ipc.errorprint.assert_called_with(
        None,
        "\x1b[1;4;31mThis is a critical message from the test_logging module.\x1b[0m",
        2,
    )

    progress("This is a progress message from the test_logging module.")
    ph_ipc.sendstatus.assert_called_with(
        None,
        1,
        "This is a progress message from the test_logging module.\x1b[0m",
        False,
    )

    warning("This is a warning message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None,
        "\x1b[33mThis is a warning message from the test_logging module.\x1b[0m",
        2,
    )

    error("This is a warning message from the test_logging module.")
    ph_ipc.debugprint.assert_called_with(
        None,
        "\x1b[1;31mThis is a warning message from the test_logging module.\x1b[0m",
        2,
    )


def test_logging_soar_not_available():
    with mock.patch.object(soar_sdk.logging, "is_soar_available", return_value=True):
        logger = PhantomLogger()
        logger.info("This is an info message from the test_logging module.")
        ph_ipc.sendstatus.assert_called_with(
            None, 1, "This is an info message from the test_logging module.", True
        )


def test_progress_not_called():
    ph_ipc.sendstatus = mock.Mock()
    logger = getLogger()
    logger.setLevel(50)
    logger.progress("Progress message not called because log level is too high")
    ph_ipc.sendstatus.assert_not_called()


def test_connector_error_caught():
    ph_ipc.errorprint.side_effect = Exception("Simulated error")

    logger = getLogger()
    logger.handler.handleError = mock.Mock()
    logger.critical("This is an error message from the test_logging module.")
    logger.handler.handleError.assert_called_once()


def test_non_existant_log_level():
    logger = getLogger()
    logger.handler.handleError = mock.Mock()
    logger.log(999, "This is a test message with an invalid log level.")
    logger.handler.handleError.assert_called_once()


def test_remove_handler_allowed():
    import logging as python_logger

    logger = getLogger()
    handler = python_logger.StreamHandler()
    logger.addHandler(handler)
    assert handler in logger.handlers
    logger.removeHandler(handler)
    assert handler not in logger.handlers


def test_remove_soar_handler_not_allowed():
    logger = getLogger()
    handler = SOARHandler()

    with pytest.raises(ValueError, match="Removing the SOARHandler is not allowed."):
        logger.removeHandler(handler)


def test_getattr_non_existant_color():
    """Tests __getattr__ returns the correct color when color is enabled."""
    color = ANSIColor(False)
    with pytest.raises(AttributeError):
        color.Random  # noqa: B018

    assert color._get_color("BLUE") == ""
