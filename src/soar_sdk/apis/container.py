import json
from typing import TYPE_CHECKING

from soar_sdk.shims.phantom.json_keys import json_keys as ph_jsons
from soar_sdk.exceptions import ActionFailure, SoarAPIError
from soar_sdk.logging import getLogger
from soar_sdk.apis.utils import is_client_authenticated

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient

logger = getLogger()


class Container:
    """API interface for managing SOAR containers.

    This class provides methods to create and manage containers within the SOAR platform.
    Containers represent security incidents or cases that group related artifacts and
    serve as the primary organizational unit for security investigations.

    Attributes:
        soar_client (SOARClient): The SOAR client instance for API communication.
    """

    def __init__(self, soar_client: "SOARClient") -> None:
        """Initialize the Container API interface.

        Sets up the container interface with default container properties and
        initializes internal container storage for unauthenticated clients.

        Args:
            soar_client (SOARClient): The SOAR client instance for API communication.
        """
        self.soar_client: SOARClient = soar_client
        self.__container_common = {
            ph_jsons.APP_JSON_DESCRIPTION: "Container added by sdk app",
            ph_jsons.APP_JSON_RUN_AUTOMATION: False,  # Don't run any playbooks, when this container is added
        }
        self.__containers: dict[int, dict] = {}

    def set_executing_asset(self, asset_id: str) -> None:
        """Set the executing asset for containers created by this interface.

        The executing asset ID will be automatically added to all containers
        created through this interface. This identifies which SOAR asset
        (app instance) is responsible for creating the container.

        Args:
            asset_id (str): The ID of the asset that will be set as the executing asset.
        """
        self.__container_common[ph_jsons.APP_JSON_ASSET_ID] = asset_id

    def create(self, container: dict, fail_on_duplicate: bool = False) -> int:
        """Create a new container in the SOAR platform.

        Creates a container with the provided data, applying default values for
        common fields if not specified. For authenticated clients, the container
        is created via the REST API. For unauthenticated clients, the container
        is stored locally for testing purposes.

        Args:
            container (dict): The container data to create. Must be JSON-serializable.
                            Common fields include:
                            - name: Container name/title
                            - description: Human-readable description
                            - severity: Severity level (low, medium, high, critical)
                            - status: Container status (new, open, closed)
                            - artifacts: List of artifacts to create with the container
                            - asset_id: ID of the executing asset (required)
            fail_on_duplicate (bool, optional): If True, raise an exception when a
                                              duplicate container is found. If False,
                                              return the existing container ID.
                                              Defaults to False.

        Returns:
            int: The ID of the created or existing container.

        Raises:
            ActionFailure: If container preparation fails or the container data
                          cannot be serialized to JSON.
            SoarAPIError: If the API request fails, the container cannot be created,
                         or if fail_on_duplicate=True and a duplicate is found.
            ValueError: If required fields (like asset_id) are missing.

        Example:
            >>> container_data = {
            ...     "name": "Suspicious Network Activity",
            ...     "description": "Detected unusual traffic patterns",
            ...     "severity": "medium",
            ...     "artifacts": [
            ...         {
            ...             "cef": {"sourceAddress": "192.168.1.100"},
            ...             "label": "ip",
            ...             "type": "network",
            ...         }
            ...     ],
            ... }
            >>> container_id = container_api.create(container_data)
            >>> print(f"Created container with ID: {container_id}")
        """
        try:
            self._prepare_container(container)
        except Exception as e:
            error_msg = f"Failed to prepare container: {e}"
            raise ActionFailure(error_msg) from e

        try:
            json.dumps(container)
        except TypeError as e:
            error_msg = (
                f"Container could not be converted to a JSON string. Error: {e!s}"
            )
            raise ActionFailure(error_msg) from e

        if is_client_authenticated(self.soar_client.client):
            endpoint = "rest/container"
            try:
                response = self.soar_client.post(endpoint, json=container)
                resp_data = response.json()
            except Exception as e:
                error_msg = f"Failed to add container: {e}"
                raise SoarAPIError(error_msg) from e

            artifact_resp_data = resp_data.get("artifacts", [])

            if "existing_container_id" in resp_data:
                if not fail_on_duplicate:
                    logger.info("Container already exists")
                    self._process_container_artifacts_response(artifact_resp_data)
                    return resp_data["existing_container_id"]
                else:
                    raise SoarAPIError("Container already exists")
            if "id" in resp_data:
                self._process_container_artifacts_response(artifact_resp_data)
                return resp_data["id"]

            msg_cause = resp_data.get("message", "NONE_GIVEN")
            message = f"Container creation failed, reason from server: {msg_cause}"
            raise SoarAPIError(message)
        else:
            artifacts = container.pop("artifacts", [])
            if artifacts and "run_automation" not in artifacts[-1]:
                artifacts[-1]["run_automation"] = True
            next_container_id = (
                max(self.__containers.keys()) if self.__containers else 0
            ) + 1
            for artifact in artifacts:
                artifact["container_id"] = next_container_id
                self.soar_client.artifact.create(artifact)
            self.__containers[next_container_id] = container
            return next_container_id

    def _prepare_container(self, container: dict) -> None:
        """Prepare container data by applying default values and validating required fields.

        This internal method updates the container dictionary with default values
        from the common container template and validates that required fields
        are present.

        Args:
            container (dict): The container data to prepare. Modified in-place.

        Raises:
            ValueError: If required fields (like asset_id) are missing.
        """
        container.update(
            {k: v for k, v in self.__container_common.items() if (not container.get(k))}
        )

        if ph_jsons.APP_JSON_ASSET_ID not in container:
            raise ValueError(f"Missing {ph_jsons.APP_JSON_ASSET_ID} key in container")

    def _process_container_artifacts_response(
        self, artifact_resp_data: list[dict]
    ) -> None:
        """Process the response data for artifacts created with a container.

        This internal method processes the API response for artifacts that were
        created along with a container, logging the results and any warnings
        for failed artifact creations.

        Args:
            artifact_resp_data (list[dict]): List of artifact response data from
                                           the container creation API call.
        """
        for resp_datum in artifact_resp_data:
            if "id" in resp_datum:
                logger.debug("Added artifact")
                continue

            if "existing_artifact_id" in resp_datum:
                logger.debug("Duplicate artifact found")
                continue

            if "failed" in resp_datum:
                msg_cause = resp_datum.get("message", "NONE_GIVEN")
                message = f"artifact addition failed, reason from server: {msg_cause}"
                logger.warning(message)
                continue

            message = "Artifact addition failed, Artifact ID was not returned"
            logger.warning(message)
