from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.action_results import ActionResult


class SOARClient(ABC):
    """
    A unified API interface for performing actions on SOAR Platform.
    Replaces previously used BaseConnector API interface.

    This interface is still a subject to change, so consider it to be WIP.
    """

    @abstractmethod
    def get_soar_base_url(self) -> str:
        pass  # pragma: no cover

    @abstractmethod
    def set_csrf_info(self, token: str, referer: str) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def handle_action(self, param: dict[str, Any]) -> None:
        """
        The actual handling method that is being called internally by BaseConnector
        at the momment.
        :param param: dict containing parameters for the action
        """
        pass  # pragma: no cover

    @abstractmethod
    def handle(
        self,
        input_data: str,
        handle: Optional[Any] = None,
    ) -> str:
        """Public method for handling the input data with the selected handler"""
        pass  # pragma: no cover

    @abstractmethod
    def initialize(self) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def finalize(self) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def add_result(self, action_result: ActionResult) -> PhantomActionResult:
        pass  # pragma: no cover

    @abstractmethod
    def get_results(self) -> list[ActionResult]:
        pass  # pragma: no cover

    @abstractmethod
    def save_progress(
        self,
        progress_str_const: str,
        *unnamed_format_args: Any,
        **named_format_args: Any,
    ) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        pass  # pragma: no cover
