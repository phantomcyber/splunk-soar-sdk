from importlib.metadata import version
import logging as python_logger
from soar_sdk.logging import getLogger, PhantomLogger
from typing import cast

# monkey patching the root logger to be the PhantomLogger
python_logger.setLoggerClass(PhantomLogger)
root_logger = cast(python_logger.RootLogger, getLogger())
python_logger.root = root_logger

__version__ = version("splunk-soar-sdk")
