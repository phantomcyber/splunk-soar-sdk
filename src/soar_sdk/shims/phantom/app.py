try:
    from phantom.app import APP_SUCCESS, APP_ERROR
except ImportError:
    APP_SUCCESS = True
    APP_ERROR = False


__all__ = ["APP_SUCCESS", "APP_ERROR"]
