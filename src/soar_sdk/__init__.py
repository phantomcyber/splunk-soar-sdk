from importlib.metadata import version
from logging import config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "color_filter": {
            "class": "soar_sdk.logging.ColorFilter",
            "color": True,
        },
    },
    "handlers": {
        "soar_handler": {
            "class": "soar_sdk.logging.SOARHandler",
            "level": "DEBUG",
            "filters": ["color_filter"],
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
        },
    },
    "root": {
        "handlers": ["console", "soar_handler"],
    },
}
config.dictConfig(LOGGING_CONFIG)

__version__ = version("splunk-soar-sdk")
