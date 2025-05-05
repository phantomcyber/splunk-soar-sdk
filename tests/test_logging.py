from unittest import mock
import pytest


from soar_sdk.connector import AppConnector
from soar_sdk.logging import getLogger, SOARHandler
from soar_sdk.colors import ANSIColor
import soar_sdk.logging


def test_logging(app_connector: AppConnector):
    app_connector.save_progress = mock.Mock()
    app_connector.debug_print = mock.Mock()
    app_connector.error_print = mock.Mock()
    app_connector.send_progress = mock.Mock()
    logger = getLogger()
    logger.info("This is an info message from the test_logging module.")
    app_connector.save_progress.assert_called_with(
        "\x1b[0mThis is an info message from the test_logging module.\x1b[0m"
    )

    logger.debug("This is a debug message from the test_logging module.")
    app_connector.debug_print.assert_called_with(
        "\x1b[2mThis is a debug message from the test_logging module.\x1b[0m", ""
    )

    logger.progress("This is a progress message from the test_logging module.")
    app_connector.send_progress.assert_called_with(
        "This is a progress message from the test_logging module.\x1b[0m"
    )

    logger.warning("This is a warning message from the test_logging module.")
    app_connector.debug_print.assert_called_with(
        "\x1b[33mThis is a warning message from the test_logging module.\x1b[0m", ""
    )

    logger.critical("This is a critical message from the test_logging module.")
    app_connector.error_print.assert_called_with(
        "\x1b[1;4;31mThis is a critical message from the test_logging module.\x1b[0m",
        "",
    )


def test_logging_soar_not_available(app_connector: AppConnector):
    with mock.patch.object(soar_sdk.logging, "is_soar_available", return_value=True):
        app_connector.save_progress = mock.Mock()
        logger = getLogger()
        logger.info("This is an info message from the test_logging module.")
        app_connector.save_progress.assert_called_with(
            "This is an info message from the test_logging module."
        )


def test_progress_not_called(app_connector: AppConnector):
    app_connector.send_progress = mock.Mock()
    logger = getLogger()
    logger.setLevel(50)
    logger.progress("Progress message not called because log level is too high")
    app_connector.send_progress.assert_not_called()


def test_connector_error_caught(app_connector: AppConnector):
    app_connector.error = mock.Mock()
    app_connector.error.side_effect = Exception("Simulated error")

    logger = getLogger()
    logger.handler.handleError = mock.Mock()
    logger.critical("This is an error message from the test_logging module.")
    logger.handler.handleError.assert_called_once()


def test_soar_client_not_initialized(app_connector: AppConnector):
    AppConnector._instance = None
    logger = getLogger()
    with pytest.raises(RuntimeError, match="SOAR client is not initialized"):
        logger.debug("Test")


def test_non_existant_log_level(app_connector: AppConnector):
    logger = getLogger()
    logger.handler.handleError = mock.Mock()
    logger.log(999, "This is a test message with an invalid log level.")
    logger.handler.handleError.assert_called_once()


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
