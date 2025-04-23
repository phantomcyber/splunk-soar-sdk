try:
    from phantom.base_connector import BaseConnector

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    import json
    import abc

    from soar_sdk.shims.phantom.action_result import ActionResult

    from typing import Union, Any

    class BaseConnector:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.action_results: list[ActionResult] = []

        @staticmethod
        def _get_phantom_base_url() -> str:
            return "https://localhost:9999/"

        def save_progress(
            self,
            progress_str_const: str,
            *unnamed_format_args: object,
            **named_format_args: object,
        ) -> None:
            return

        def debug_print(
            self,
            _tag: str,
            _dump_object: Union[str, list, dict, ActionResult, Exception],
        ) -> None:
            print(_tag, _dump_object)

        def get_action_results(self) -> list[ActionResult]:
            return self.action_results

        def add_action_result(self, action_result: ActionResult) -> ActionResult:
            self.action_results.append(action_result)
            return action_result

        def get_action_identifier(self) -> str:
            return self.action_identifier

        @abc.abstractmethod
        def handle_action(self, param: dict[str, Any]) -> None:
            pass

        def _handle_action(self, in_json: str, handle: int) -> str:
            input_object = json.loads(in_json)

            self.action_identifier = input_object.get("identifier", "")
            self.config = input_object.get("config", {})
            param_array = input_object.get("parameters") or [{}]
            for param in param_array:
                self.handle_action(param)

            return in_json

        def get_config(self) -> dict:
            return self.config

        def save_state(self, state: dict) -> None:
            self.state = state

        def load_state(self) -> dict:
            return self.state

        def _set_csrf_info(self, token: str, referer: str) -> None:
            pass

        def finalize(self) -> bool:
            return True

        def initialize(self) -> bool:
            return True


__all__ = ["BaseConnector"]
