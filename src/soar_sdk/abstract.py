from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from soar_sdk.input_spec import InputSpecification
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
        pass

    @abstractmethod
    def set_csrf_info(self, token: str, referer: str) -> None:
        pass

    @abstractmethod
    def handle_action(self, param: dict[str, Any]) -> None:
        """
        The actual handling method that is being called internally by BaseConnector
        at the momment.
        :param param: dict containing parameters for the action
        """
        pass

    @abstractmethod
    def handle(
        self,
        input_data: InputSpecification,
        handle: Optional[int] = None,
    ) -> str:
        """Public method for handling the input data with the selected handler"""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def finalize(self) -> bool:
        pass

    @abstractmethod
    def add_result(self, action_result: ActionResult) -> PhantomActionResult:
        pass

    @abstractmethod
    def get_results(self) -> list[ActionResult]:
        pass

    @abstractmethod
    def save_progress(
        self,
        progress_str_const: str,
        *unnamed_format_args: object,
        **named_format_args: object,
    ) -> None:
        pass

    @abstractmethod
    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        pass
