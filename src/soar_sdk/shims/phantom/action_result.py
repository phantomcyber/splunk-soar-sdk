try:
    from phantom.action_result import *  # noqa: F403
except ImportError:
    from typing import Optional, Union

    class ActionResult:
        def __init__(self, param: Optional[dict] = None) -> None:
            self.status = False

            if param is None:
                self.param = {}
            elif type(param) is dict:
                self.param = param
            else:
                raise TypeError("param must be dict")

        def set_status(
            self,
            status_code: Union[bool, int],
            _status_message: str = "",
            _exception: Optional[Exception] = None,
        ) -> bool:
            self.status = bool(status_code)
            return self.status

        def get_status(self) -> bool:
            return self.status
