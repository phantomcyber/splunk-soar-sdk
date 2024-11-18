import typing
from typing import Any, Optional, Union

from phantom.base_connector import BaseConnector
from soar_sdk.action_results import ActionResult

from .abstract import SOARClient

if typing.TYPE_CHECKING:
    pass


class LegacyConnectorAdapter(SOARClient):

    def __init__(self, legacy_connector_class: type[BaseConnector]) -> None:
        self.connector = legacy_connector_class()

    def get_soar_base_url(self) -> str:
        return self.connector._get_phantom_base_url()

    def set_csrf_info(self, token: str, referer: str) -> None:
        self.connector._set_csrf_info(token, referer)

    def handle_action(self, param):
        self.connector.handle_action(param)

    def handle(
        self,
        input_data: str,
        handle: Optional[Any] = None,
    ) -> str:
        return self.connector._handle_action(input_data, handle)

    def initialize(self) -> bool:
        return self.connector.initialize()

    def finalize(self) -> bool:
        return self.connector.finalize()

    def add_result(self, action_result: ActionResult) -> None:
        return self.connector.add_action_result(action_result)

    def get_results(self):
        return self.connector.get_action_results()

    def save_progress(
        self,
        progress_str_const: str,
        *unnamed_format_args: Any,
        **named_format_args: Any,
    ) -> None:
        return self.connector.save_progress(
            progress_str_const, *unnamed_format_args, **named_format_args
        )

    def debug(
        self,
        tag: str,
        dump_object: Union[str, list, dict, ActionResult, Exception] = "",
    ) -> None:
        self.connector.debug_print(tag, dump_object)
