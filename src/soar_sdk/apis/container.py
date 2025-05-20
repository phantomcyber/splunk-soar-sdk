import json

from soar_sdk.connector import ApiManager
from soar_sdk.shims.phantom.json_keys import json_keys as ph_jsons
from soar_sdk.exceptions import ActionFailure, SoarAPIError
from soar_sdk.logging import getLogger


class Container:
    def __init__(self, api_manager: ApiManager):
        self.api_manager: ApiManager = api_manager
        self.__container_common = {
            ph_jsons.APP_JSON_DESCRIPTION: "Container added by sdk app",
            ph_jsons.APP_JSON_RUN_AUTOMATION: False,  # Don't run any playbooks, when this container is added
        }
        self.__containers = {}
        self.logger = getLogger()

    def create(self, container: dict, fail_on_duplicate: bool) -> None:
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

        if self.api_manager.is_authenticated():
            client = self.api_manager.get_client()
            try:
                response = client.post("rest/container", json=container)
            except Exception as e:
                error_msg = f"Failed to add container: {e}"
                raise SoarAPIError(error_msg) from e

            resp_data = response.json()
            if "existing_container_id" in resp_data:
                return (
                    not fail_on_duplicate,
                    "Container already exists",
                    resp_data.get("existing_container_id"),
                )

            if resp_data.get("failed"):
                msg_cause = resp_data.get("message", "NONE_GIVEN")
                message = f"Container creation failed, reason from server: {msg_cause}"
                raise SoarAPIError(message)

            artifact_resp_data = resp_data.get("artifacts", [])
            self._process_container_artifacts_response(artifact_resp_data)
        else:
            artifacts = container.pop("artifacts", [])
            next_container_id = (
                max(self.__containers.keys()) if self.__containers else 0
            ) + 1
            for artifact in artifacts:
                artifact["container_id"] = next_container_id
                self._save_artifact(artifact)
            self.__containers[next_container_id] = container

    def _prepare_container(self, container: dict) -> None:
        if ph_jsons.APP_JSON_ASSET_ID not in container:
            asset_id = container.get(ph_jsons.APP_JSON_INGEST_APP_ID)
            if not asset_id:
                raise ValueError(
                    f"Missing {ph_jsons.APP_JSON_ASSET_ID} key in container"
                )
            self.__container_common[ph_jsons.APP_JSON_ASSET_ID] = asset_id

        container.update(
            {k: v for k, v in self.__container_common.items() if (not container.get(k))}
        )

        if "artifacts" in container and len(container["artifacts"]) > 0:
            if "run_automation" not in container["artifacts"][-1]:
                container["artifacts"][-1]["run_automation"] = True
            for artifact in container["artifacts"]:
                artifact.update(
                    {
                        k: v
                        for k, v in self._artifact_common.items()
                        if (not artifact.get(k))
                    }
                )

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
