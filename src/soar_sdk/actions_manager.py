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
    """Manages the execution of an action."""

    def __init__(self) -> None:
        super().__init__()

        self._actions: dict[str, Action] = {}
        self.ingestion_state: dict = {}
        self.auth_state: dict = {}
        self.asset_cache: dict = {}

    def get_action(self, identifier: str) -> Optional[Action]:
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

    def handle(
        self, input_data: InputSpecification, handle: Optional[int] = None
    ) -> str:
        """Runs handling of the input data on connector."""
        action_id = input_data.identifier
        if self.get_action(action_id):
            self.print_progress_message = True
            return self._handle_action(input_data.json(), handle or 0)
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
                params = handler.meta.parameters.parse_obj(param)
            except (ValueError, ValidationError) as e:
                self.save_progress(
                    f"Validation Error - the params data for action could not be parsed: {e!s}"
                )
                return
            handler(params)

        else:
            raise RuntimeError(f"Action {action_id} not found.")

    def initialize(self) -> bool:
        """Load asset state into memory at initialization, splitting it into 3 categories.

        Asset state is used to store data that needs to be accessed across actions.
        Chiefly, it is used to store ingestion state, authentication state, and/or
        used as an asset cache. Returns True only to conform with the BaseConnector interface.
        """
        state = self.load_state() or {}
        self.ingestion_state = state.get(_INGEST_STATE_KEY, {})
        self.auth_state = state.get(_AUTH_STATE_KEY, {})
        self.asset_cache = state.get(_CACHE_STATE_KEY, {})

        return True

    def finalize(self) -> bool:
        """Save asset state from memory into persistent storage at finalization.

        Joins the SDK's 3 categories of asset state into a single dictionary, conforming
        to the platform's expectations, and saves it.
        Returns True only to conform with the BaseConnector interface.
        """
        state = {
            _INGEST_STATE_KEY: self.ingestion_state,
            _AUTH_STATE_KEY: self.auth_state,
            _CACHE_STATE_KEY: self.asset_cache,
        }
        self.save_state(state)
        return True

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

    @classmethod
    def get_soar_base_url(cls) -> str:
        """Get the base URL of the Splunk SOAR instance this app is running on."""
        return cls._get_phantom_base_url()
