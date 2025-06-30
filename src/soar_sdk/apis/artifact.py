import json
from typing import TYPE_CHECKING

from soar_sdk.exceptions import ActionFailure, SoarAPIError
from soar_sdk.shims.phantom.json_keys import json_keys as ph_jsons
from soar_sdk.shims.phantom.consts import consts as ph_consts
from soar_sdk.apis.utils import is_client_authenticated
from soar_sdk.logging import getLogger

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient

logger = getLogger()


class Artifact:
    """API interface for managing SOAR artifacts.

    This class provides methods to create and manage artifacts within SOAR.

    Attributes:
        soar_client (SOARClient): The SOAR client instance for API communication.
    """

    def __init__(self, soar_client: "SOARClient") -> None:
        """Initialize the Artifact API interface.

        Sets up the artifact interface with default artifact properties and
        initializes internal artifact storage for unauthenticated clients.

        Args:
            soar_client (SOARClient): The SOAR client instance for API communication.
        """
        self.soar_client: SOARClient = soar_client
        self._artifact_common = {
            ph_jsons.APP_JSON_LABEL: ph_consts.APP_DEFAULT_ARTIFACT_LABEL,
            ph_jsons.APP_JSON_TYPE: ph_consts.APP_DEFAULT_ARTIFACT_TYPE,
            ph_jsons.APP_JSON_DESCRIPTION: "Artifact added by sdk app",
            ph_jsons.APP_JSON_RUN_AUTOMATION: False,  # Don't run any playbooks, when this artifact is added
        }
        self.__artifacts: dict[int, dict] = {}

    def create(self, artifact: dict) -> int:
        """Create a new artifact in the SOAR platform.

        Creates an artifact with the provided data, applying default values for
        common fields if not specified. For authenticated clients, the artifact
        is created via the REST API. For unauthenticated clients, the artifact
        is stored locally for testing purposes.

        Args:
            artifact (dict): The artifact data to create. Must be JSON-serializable.
                           Common fields include:
                           - container_id: ID of the container to associate with
                           - cef: Common Event Format data
                           - label: Artifact label (defaults to 'artifact')
                           - type: Artifact type (defaults to 'generic')
                           - description: Human-readable description

        Returns:
            int: The ID of the created artifact.

        Raises:
            ActionFailure: If the artifact data cannot be serialized to JSON.
            SoarAPIError: If the API request fails or the artifact cannot be created.
                         For unauthenticated clients, raised if no container_id is provided.

        Example:
            >>> artifact_data = {
            ...     "container_id": 123,
            ...     "cef": {"sourceAddress": "192.168.1.1"},
            ...     "label": "ip",
            ...     "type": "network",
            ... }
            >>> artifact_id = artifact_api.create(artifact_data)
            >>> print(f"Created artifact with ID: {artifact_id}")
        """
        artifact.update(
            {k: v for k, v in self._artifact_common.items() if (not artifact.get(k))}
        )
        try:
            json.dumps(artifact)
        except TypeError as e:
            error_msg = (
                f"Artifact could not be converted to a JSON string. Error: {e!s}"
            )
            raise ActionFailure(error_msg) from e

        if is_client_authenticated(self.soar_client.client):
            endpoint = "rest/artifact"
            try:
                response = self.soar_client.post(endpoint, json=artifact)
            except Exception as e:
                error_msg = f"Failed to add artifact: {e}"
                raise SoarAPIError(error_msg) from e

            resp_data = response.json()

            if "existing_artifact_id" in resp_data:
                logger.info("Artifact already exists")
                return resp_data["existing_artifact_id"]

            if "id" in resp_data:
                return resp_data["id"]

            msg_cause = resp_data.get("message", "NONE_GIVEN")
            message = f"Artifact addition failed, reason from server: {msg_cause}"
            raise SoarAPIError(message)
        else:
            if "container_id" not in artifact:
                message = "Artifact addition failed, no container ID given"
                raise SoarAPIError(message)
            next_artifact_id = (
                max(self.__artifacts.keys()) if self.__artifacts else 0
            ) + 1
            self.__artifacts[next_artifact_id] = artifact
            return next_artifact_id
