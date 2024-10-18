from typing import Optional

from phantom.action_result import ActionResult as PhantomActionResult


class ActionResult(PhantomActionResult):

    def __init__(self, status, message, param: Optional[dict] = None) -> None:
        super().__init__(param)
        self.set_status(status, message)


class SuccessActionResult(ActionResult):
    def __init__(self, message, param: Optional[dict] = None) -> None:
        super().__init__(True, message, param)


class ErrorActionResult(ActionResult):
    def __init__(self, message, param: Optional[dict] = None) -> None:
        super().__init__(True, message, param)
