import json
from typing import TYPE_CHECKING

from soar_sdk.shims.phantom.json_keys import json_keys as ph_jsons
from soar_sdk.exceptions import ActionFailure, SoarAPIError
from soar_sdk.logging import getLogger
from soar_sdk.apis.utils import is_client_authenticated

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient


class Container:
    """
    API interface for containers.
    """

    def __init__(self, soar_client: "SOARClient") -> None:
        self.soar_client: SOARClient = soar_client
        self.__container_common = {
            ph_jsons.APP_JSON_DESCRIPTION: "Container added by sdk app",
            ph_jsons.APP_JSON_RUN_AUTOMATION: False,  # Don't run any playbooks, when this container is added
        }
        self.__containers: dict[int, dict] = {}
        self.logger = getLogger()

    def set_executing_asset(self, asset_id: str) -> None:
        """
        Set the executing asset for the container.
        """
        self.__container_common[ph_jsons.APP_JSON_ASSET_ID] = asset_id

    def create(self, container: dict, fail_on_duplicate: bool = False) -> int:
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
                    self.logger.info("Container already exists")
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
        container.update(
            {k: v for k, v in self.__container_common.items() if (not container.get(k))}
        )

        if ph_jsons.APP_JSON_ASSET_ID not in container:
            raise ValueError(f"Missing {ph_jsons.APP_JSON_ASSET_ID} key in container")

    def _process_container_artifacts_response(
        self, artifact_resp_data: list[dict]
    ) -> None:
        for resp_datum in artifact_resp_data:
            if "id" in resp_datum:
                self.logger.debug("Added artifact")
                continue

            if "existing_artifact_id" in resp_datum:
                self.logger.debug("Duplicate artifact found")
                continue

            if "failed" in resp_datum:
                msg_cause = resp_datum.get("message", "NONE_GIVEN")
                message = f"artifact addition failed, reason from server: {msg_cause}"
                self.logger.warning(message)
                continue

            message = "Artifact addition failed, Artifact ID was not returned"
            self.logger.warning(message)
