import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.input_spec import InputSpecification
from soar_sdk.logging import getLogger
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.shims.phantom.install_info import is_onprem_broker_install
from soar_sdk.types import Action

logger = getLogger()


class ActionsManager(BaseConnector):
    """Manages the execution of an action."""

    def __init__(self) -> None:
        super().__init__()

        self._actions: dict[str, Action] = {}
        self.__app_dir: Path | None = None
        self.supports_es_polling: bool = False

    def get_action(self, identifier: str) -> Action | None:
        """Convenience method for getting an Action callable from its identifier.

        Returns None if there are no actions managed by this object matching the given
        identifier.
        """
        return self.get_actions().get(identifier)

    def get_actions(self) -> dict[str, Action]:
        """Get a dictionary mapping from identifier to Action callables."""
        return self._actions

    def get_actions_meta_list(self) -> list[ActionMeta]:
        """Get a list of the ActionMeta objects associated with this object's Actions."""
        return [action.meta for action in self.get_actions().values()]

    def set_action(self, action_identifier: str, wrapped_function: Action) -> None:
        """Sets the handler for the function that can be called by the BaseConnector.

        The wrapped function called by the BaseConnector will be called using the old
        backward-compatible declaration.

        :param action_identifier: name of the action
        :param wrapped_function: the wrapped function that should
                                 be called by the BaseConnector
        :return: None
        """
        self._actions[action_identifier] = wrapped_function

    def handle(self, input_data: InputSpecification, handle: int | None = None) -> str:
        """Runs handling of the input data on connector."""
        action_id = input_data.identifier
        if self.get_action(action_id):
            self.print_progress_message = True
            return self._handle_action(input_data.model_dump_json(), handle or 0)
        else:
            raise RuntimeError(
                f"Action {action_id} not recognized"
            )  # TODO: replace with a valid lack of action handling

    def handle_action(self, param: dict[str, Any]) -> None:
        """The central action execution function BaseConnector expects to be overridden.

        Given the input parameter dictionary from Splunk SOAR, find the Action function
        referred to by the input, parse the parameters into the appropriate Pydantic model,
        and execute the action.
        """
        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()
        logger.debug(f"action_id {action_id}")

        if handler := self.get_action(action_id):
            try:
                params = handler.meta.parameters.model_validate(param)
            except (ValueError, ValidationError) as e:
                self.save_progress(
                    f"Validation Error - the params data for action could not be parsed: {e!s}"
                )
                return
            handler(params)

        else:
            raise RuntimeError(f"Action {action_id} not found.")

    def add_result(self, action_result: PhantomActionResult) -> PhantomActionResult:
        """Wrapper for BaseConnector's add_action_result method."""
        return self.add_action_result(action_result)

    def get_results(self) -> list[PhantomActionResult]:
        """Wrapper for BaseConnector's get_action_results method."""
        return self.get_action_results()

    def add_exception(self, exception: Exception) -> None:
        """Public method for adding an exception to an app run result set."""
        self._BaseConnector__conn_result.add_exception(exception)

    def set_csrf_info(self, token: str, referer: str) -> None:
        """Public method for setting the CSRF token in connector."""
        self._set_csrf_info(token, referer)

    def get_app_dir(self) -> str:
        """Override get_app_dir to fix path issue on automation brokers < 7.1.0.

        Returns APP_HOME directly on brokers, which contains the correct SDK app path.
        """
        # If the app dir has been overridden by calling `override_app_dir`, return that
        if self.__app_dir:
            return self.__app_dir.as_posix()

        # Remove when 7.1.0 is the min supported broker version
        remove_when_soar_newer_than("7.1.1")
        # On AB, APP_HOME is set by spawn to the full app path at runtime
        if is_onprem_broker_install():
            return os.getenv("APP_HOME", "")

        # For non-broker just proceed as we did before
        return super().get_app_dir()

    @classmethod
    def get_soar_base_url(cls) -> str:
        """Get the base URL of the Splunk SOAR instance this app is running on."""
        return cls._get_phantom_base_url()

    def override_app_dir(self, app_dir: Path) -> None:
        """Request that the given app_dir be used, instead of whatever super().get_app_dir() returns.

        This is useful for contexts such as Webhooks, where the app dir isn't necessarily the cwd, but we still need to load the app JSON reliably.
        """
        self.__app_dir = app_dir

    def _get_state_file_path(self, asset_id: str) -> Path:
        """Get the state file path for an asset."""
        return Path(self.get_state_dir()) / f"{asset_id}_state.json"

    def load_state_from_file(self, asset_id: str) -> dict:
        """Load state directly from file."""
        state_file = self._get_state_file_path(asset_id)
        if state_file.exists():
            return json.loads(state_file.read_text())
        return {}

    def save_state_to_file(self, asset_id: str, state: dict) -> None:
        """Save state directly to file using atomic write."""
        state_file = self._get_state_file_path(asset_id)
        state_file.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=state_file.parent)
        tmp_file = Path(tmp_path)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(state))
            shutil.move(tmp_file, state_file)
        except Exception:
            if tmp_file.exists():
                tmp_file.unlink()
            raise

    def reload_state_from_file(self, asset_id: str) -> dict:
        """Reload state from file and update in-memory state.

        Needed for OAuth flow where one process (webhook) updates the state file and another process (action) needs to see those changes.
        """
        state = self.load_state_from_file(asset_id)
        if state:
            self.save_state(state)
        return state
