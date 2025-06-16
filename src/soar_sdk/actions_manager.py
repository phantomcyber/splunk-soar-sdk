from typing import Optional, Any

from soar_sdk.input_spec import InputSpecification
from soar_sdk.shims.phantom.base_connector import BaseConnector

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action
from pydantic import ValidationError
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult
from soar_sdk.logging import getLogger


_INGEST_STATE_KEY = "ingestion_state"
_AUTH_STATE_KEY = "auth_state"
_CACHE_STATE_KEY = "asset_cache"

logger = getLogger()


class ActionsManager(BaseConnector):
    """
    Manages the execution of an action.
    """

    def __init__(self) -> None:
        super().__init__()

        self._actions: dict[str, Action] = {}
        self.ingestion_state: dict = {}
        self.auth_state: dict = {}
        self.asset_cache: dict = {}

    def get_action(self, identifier: str) -> Optional[Action]:
        return self.get_actions().get(identifier)

    def get_actions(self) -> dict[str, Action]:
        return self._actions

    def get_actions_meta_list(self) -> list[ActionMeta]:
        return [action.meta for action in self.get_actions().values()]

    def set_action(self, action_identifier: str, wrapped_function: Action) -> None:
        """
        Sets the handler for the function that can be called by the BaseConnector.
        The wrapped function called by the BaseConnector will be called using the old
        backward-compatible declaration.

        :param action_identifier: name of the action
        :param wrapped_function: the wrapped function that should
                                 be called by the BaseConnector
        :return: None
        """
        self._actions[action_identifier] = wrapped_function

    def handle(
        self, input_data: InputSpecification, handle: Optional[int] = None
    ) -> str:
        """
        Runs handling of the input data on connector
        """
        action_id = input_data.identifier
        if self.get_action(action_id):
            self.print_progress_message = True
            return self._handle_action(input_data.json(), handle or 0)
        else:
            raise RuntimeError(
                f"Action {action_id} not recognized"
            )  # TODO: replace with a valid lack of action handling

    def handle_action(self, param: dict[str, Any]) -> None:
        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()
        logger.debug(f"action_id {action_id}")

        if handler := self.get_action(action_id):
            try:
                params = handler.meta.parameters.parse_obj(param)
            except (ValueError, ValidationError):
                # FIXME: Consider adding more details to this error, but be aware
                #  of possible PIIs.
                self.save_progress(
                    "Validation Error - the params data for action could not be parsed"
                )
                return
            handler(params)

        else:
            raise RuntimeError(f"Action {action_id} not found.")

    def initialize(self) -> bool:
        # Load the state in initialize, use it to store data
        # that needs to be accessed across actions
        state = self.load_state() or {}
        self.ingestion_state = state.get(_INGEST_STATE_KEY, {})
        self.auth_state = state.get(_AUTH_STATE_KEY, {})
        self.asset_cache = state.get(_CACHE_STATE_KEY, {})

        return True

    def finalize(self) -> bool:
        state = {
            _INGEST_STATE_KEY: self.ingestion_state,
            _AUTH_STATE_KEY: self.auth_state,
            _CACHE_STATE_KEY: self.asset_cache,
        }
        self.save_state(state)
        return True

    def add_result(self, action_result: PhantomActionResult) -> PhantomActionResult:
        return self.add_action_result(action_result)

    def get_results(self) -> list[PhantomActionResult]:
        return self.get_action_results()

    def add_exception(self, exception: Exception) -> None:
        self._BaseConnector__conn_result.add_exception(exception)

    def set_csrf_info(self, token: str, referer: str) -> None:
        """Public method for setting the CSRF token in connector."""
        self._set_csrf_info(token, referer)

    @classmethod
    def get_soar_base_url(cls) -> str:
        return cls._get_phantom_base_url()
