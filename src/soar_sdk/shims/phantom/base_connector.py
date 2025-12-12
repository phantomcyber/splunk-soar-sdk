try:
    from phantom.base_connector import BaseConnector

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from pathlib import Path
from typing import TYPE_CHECKING

from soar_sdk.compat import remove_when_soar_newer_than

if TYPE_CHECKING or not _soar_is_available:
    import abc
    import hashlib
    import json
    import os
    from contextlib import suppress
    from typing import Any

    from soar_sdk.shims.phantom.action_result import ActionResult
    from soar_sdk.shims.phantom.connector_result import ConnectorResult

    class BaseConnector:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.action_results: list[ActionResult] = []
            self.__conn_result: ConnectorResult
            self.__conn_result = ConnectorResult()
            self.__state: dict = {}
            self.__app_json: dict = {}

        @staticmethod
        def _get_phantom_base_url() -> str:
            return "https://localhost:9999/"

        def get_product_installation_id(self) -> str:
            """
            The real BaseConnector returns a hash of the local system's SSL cert.
            Our fake will return the same value every time you call it in a single action, much like the real one.
            However, to simulate the fact that different SOAR nodes should return unique values, the value returned
            by this function will change across full script invocations, by incorporating the current PID
            """
            content = f"soar-sdk-{os.getpid()}".encode()
            return hashlib.sha256(content).hexdigest()

        def send_progress(
            self,
            progress_str_const: str,
            *unnamed_format_args: object,
            **named_format_args: object,
        ) -> None:
            with suppress(IndexError, KeyError, ValueError):
                progress_str_const = progress_str_const.format(
                    *unnamed_format_args, **named_format_args
                )

            print(progress_str_const)

        def save_progress(
            self,
            progress_str_const: str,
            *unnamed_format_args: object,
            **named_format_args: object,
        ) -> None:
            with suppress(IndexError, KeyError, ValueError):
                progress_str_const = progress_str_const.format(
                    *unnamed_format_args, **named_format_args
                )

            print(progress_str_const)

        def error_print(
            self,
            _tag: str,
            _dump_object: str | list | dict | ActionResult | Exception = "",
        ) -> None:
            print(_tag, _dump_object)

        def debug_print(
            self,
            _tag: str,
            _dump_object: str | list | dict | ActionResult | Exception = "",
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

        def save_container(
            self, container: dict, fail_on_duplicate: bool = False
        ) -> tuple[bool, str, int | None]:
            return True, "Container saved successfully", 1

        def save_artifacts(
            self, artifacts: list[dict]
        ) -> tuple[bool, str, int | None | list[int]]:
            return True, "Artifacts saved successfully", [1]

        def get_config(self) -> dict:
            return self.config

        def get_app_id(self) -> str:
            return self.__app_json.get("appid", "")

        def get_state_dir(self) -> str:
            phantom_home = os.getenv("PHANTOM_HOME", "/opt/phantom")
            return f"{phantom_home}/local_data/app_states/{self.get_app_id()}/"

        def save_state(self, state: dict) -> None:
            self.__state = state

        def load_state(self) -> dict:
            return self.__state

        def _set_csrf_info(self, token: str, referer: str) -> None:
            pass

        def finalize(self) -> bool:
            return True

        def initialize(self) -> bool:
            return True

        def get_app_dir(self) -> str:
            # Remove when 7.1.0 is the min supported broker version
            remove_when_soar_newer_than("7.1.1")
            return Path.cwd().as_posix()

        def _load_app_json(self) -> None:
            pass


__all__ = ["BaseConnector"]
