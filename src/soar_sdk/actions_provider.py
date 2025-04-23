from typing import Optional

from soar_sdk.input_spec import InputSpecification
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.abstract import SOARClient
from soar_sdk.adapters import LegacyConnectorAdapter
from soar_sdk.connector import AppConnector
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action


class ActionsProvider:
    """
    Supports working on both: old legacy connectors and new connectors.
    If you provide legacy connector class from the old implementation, it will be
    adapted to the new interfaces and used by App to properly run old handlers.
    """

    def __init__(
        self, legacy_connector_class: Optional[type[BaseConnector]] = None
    ) -> None:
        self.legacy_soar_client: Optional[SOARClient] = None
        if legacy_connector_class is not None:
            self.legacy_soar_client = LegacyConnectorAdapter(legacy_connector_class)

        self.soar_client: AppConnector = AppConnector(self)

        self._actions: dict[str, Action] = {}

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
            return self.soar_client.handle(input_data, handle)
        elif self.legacy_soar_client:
            return self.legacy_soar_client.handle(input_data, handle)
        else:
            raise RuntimeError(
                f"Action {action_id} not recognized"
            )  # TODO: replace with a valid lack of action handling
