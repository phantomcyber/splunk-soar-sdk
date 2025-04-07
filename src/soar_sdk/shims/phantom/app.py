try:
    from phantom.app import *  # noqa: F403
except ImportError:
    APP_SUCCESS = True
    APP_ERROR = False
