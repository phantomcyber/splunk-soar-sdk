from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from soar_sdk.action_results import ActionResult


class SOARClient(ABC):
    """
    A unified API interface for performing actions on SOAR Platform.
    Replaces previously used BaseConnector API interface.

    This interface is still a subject to change, so consider it to be WIP.
    """

    @abstractmethod
    def get_soar_base_url(self):
        pass

    @abstractmethod
    def set_csrf_info(self, token: str, referer: str) -> None:
        pass

    @abstractmethod
    def handle_action(self, param):
        pass

    @abstractmethod
    def handle(
        self,
        input_data: str,
        handle: Optional[Any],
    ) -> str:
        """Public method for handling the input data with the selected handler"""
        return ""

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def finalize(self) -> bool:
        pass

    @abstractmethod
    def add_result(self, action_result: ActionResult):
        pass

    @abstractmethod
    def get_results(self):
        pass

    @abstractmethod
    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        pass
