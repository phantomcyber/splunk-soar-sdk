from __future__ import annotations

import logging
import ssl
import time
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import httpx
import urllib3
import websockets

from soar_sdk.abstract import SOARClient
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault

from . import phantom_constants


class PhantomInstance(SOARClient):
    """Handle interaction with a Phantom instance."""

    def __init__(
        self,
        base_url: str,
        ph_user: str,
        ph_pass: str,
        verify_certs: bool = False,
    ):
        super().__init__()
        self.base_url = base_url
        self.verify_certs = verify_certs
        self.ph_user = ph_user
        self.ph_pass = ph_pass

        if not verify_certs:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        transport = httpx.HTTPTransport(retries=5, verify=verify_certs)
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=(ph_user, ph_pass),
            verify=verify_certs,
            transport=transport,
            timeout=httpx.Timeout(phantom_constants.DEFAULT_REQUEST_TIMEOUT_IN_SECONDS),
        )

        self._vault_api = Vault(soar_client=self)
        self._artifacts_api = Artifact(soar_client=self)
        self._containers_api = Container(soar_client=self)

    @property
    def client(self) -> httpx.Client:
        """The HTTP client used for making requests to the SOAR API."""
        return self._client

    @property
    def vault(self) -> Vault:
        """The SOAR Vault API."""
        return self._vault_api

    @property
    def artifact(self) -> Artifact:
        """The SOAR Artifacts API."""
        return self._artifacts_api

    @property
    def container(self) -> Container:
        """The SOAR Containers API."""
        return self._containers_api

    def get_executing_container_id(self) -> int:
        """Return the current Container ID passed in the Connector Run Action JSON."""
        return 0

    def get_asset_id(self) -> str:
        """Return the current Asset ID passed in the Connector Run Action JSON."""
        return ""

    def update_client(self, soar_auth, asset_id: str, container_id: int = 0) -> None:
        """Update the SOAR client with the given authentication and asset ID."""
        pass

    def set_summary(self, summary) -> None:
        """Set the custom summary object for the action run."""
        pass

    def set_message(self, message: str) -> None:
        """Set the summary message for the action run."""
        pass

    def get_summary(self):
        """Get the summary for the action run."""
        return None

    def get_message(self) -> str:
        """Get the summary message for the action run."""
        return ""

    def get_endpoint(
        self,
        endpoint: str,
        params: dict | None = None,
        timeout: int = phantom_constants.DEFAULT_REQUEST_TIMEOUT_IN_SECONDS,
        raise_on_fail: bool = True,
    ):
        """Send a GET request to the specified endpoint on the phantom instance."""
        response = self.get(
            endpoint,
            params=params,
            timeout=httpx.Timeout(timeout),
        )
        if raise_on_fail:
            response.raise_for_status()
        return response

    def post_endpoint(
        self,
        endpoint: str,
        data: dict | None = None,
        json_data: dict | None = None,
        timeout: int = phantom_constants.DEFAULT_REQUEST_TIMEOUT_IN_SECONDS,
        raise_on_fail: bool = True,
    ):
        """Send a POST request to the specified endpoint on the phantom instance."""
        response = self.post(
            endpoint,
            data=data,
            json=json_data,
            timeout=httpx.Timeout(timeout),
        )
        if raise_on_fail:
            response.raise_for_status()
        return response

    def delete_endpoint(
        self,
        endpoint: str,
        object_id: int,
        timeout: int = phantom_constants.DEFAULT_REQUEST_TIMEOUT_IN_SECONDS,
        raise_on_fail: bool = True,
    ):
        """Send a DELETE request to the specified endpoint on the phantom instance."""
        response = self.delete(
            f"{endpoint}/{object_id}",
            timeout=httpx.Timeout(timeout),
        )
        if raise_on_fail:
            response.raise_for_status()
        return response

    def get_version(self) -> str:
        """Get the phantom instance version."""
        return self.get_endpoint(phantom_constants.ENDPOINT_VERSION).json()["version"]

    def create_label(self, label: str) -> bool:
        """Create a label."""
        data = {
            "add_label": True,
            "label_name": label,
        }
        create_label_request = self.post_endpoint(
            phantom_constants.ENDPOINT_EVENT_SETTINGS, json_data=data
        )
        return create_label_request.json()["success"]

    def delete_label(self, label: str) -> bool:
        """Delete a label."""
        data = {
            "remove_label": True,
            "label_name": label,
        }
        logging.info('Deleting container label "%s".', label)
        delete_label_request = self.post_endpoint(
            phantom_constants.ENDPOINT_EVENT_SETTINGS, json_data=data
        )
        return delete_label_request.json()["success"]

    def create_container(
        self,
        container_name: str,
        label: str,
        tags: list | None = None,
        status: str = "new",
    ) -> int:
        """Create a container."""
        data = {
            "name": container_name,
            "label": label,
            "tags": tags if tags is not None else [],
            "status": status,
        }
        create_container_request = self.post_endpoint(
            phantom_constants.ENDPOINT_CONTAINER, json_data=data
        )
        container_id = create_container_request.json()["id"]
        return container_id

    def find_containers_from_asset(self, asset_id: int) -> list[dict]:
        """Find containers that were created by a given asset"""
        response = self.get_endpoint(
            phantom_constants.ENDPOINT_CONTAINER, params={"_filter_asset_id": asset_id}
        )
        return response.json()["data"]

    def delete_container(self, container_id: int):
        """Delete a container."""
        logging.info("Deleting container with ID %s.", container_id)
        self.delete_endpoint(phantom_constants.ENDPOINT_CONTAINER, container_id)

    def get_action_results(
        self, action_id: int, include_expensive: bool = True
    ) -> dict:
        """Get the results of a triggered action."""
        action_query_params = {}
        if include_expensive:
            action_query_params["include_expensive"] = True

        url = f"{phantom_constants.ENDPOINT_RUN_ACTION}/{action_id}/app_runs"
        return self.get_endpoint(url, action_query_params).json()

    def get_action_status(self, action_id: int) -> dict:
        """Get the status of a triggered action."""
        url = f"{phantom_constants.ENDPOINT_RUN_ACTION}/{action_id}"
        return self.get_endpoint(url).json()

    def get_app_info(
        self, name: str | None = None, vendor: str | None = None, pretty: bool = True
    ) -> dict:
        """Query for app information."""
        app_query_params = {}
        if name:
            app_query_params["_filter_name"] = f'"{name}"'
        if vendor:
            app_query_params["_filter_product_vendor"] = f'"{vendor}"'
        if pretty:
            app_query_params["pretty"] = True
        app_info_request = self.get_endpoint(
            phantom_constants.ENDPOINT_APP, app_query_params
        )

        app_info_json = app_info_request.json()

        return app_info_json

    def get_asset(self, name: str) -> dict:
        """Query for an asset by name."""
        asset_query_params = {"_filter_name": f'"{name}"'}
        asset_request = self.get_endpoint(
            phantom_constants.ENDPOINT_ASSET, asset_query_params
        )

        asset_request_json = asset_request.json()
        num_assets_found = asset_request_json["count"]
        assert num_assets_found >= 1, f'Found no assets with name "{name}"'
        if num_assets_found > 1:
            logging.warning('Found %d assets with name "%s".', num_assets_found, name)

        return asset_request_json

    def insert_asset(self, asset: dict, overwrite: bool = True) -> int:
        """Insert an asset."""
        asset_name = asset["name"]
        if any(char.isupper() for char in asset_name):
            logging.error(
                "Phantom lowercases all asset names on insertion. The asset should be updated "
                "to have a lowercase name to match the true value that will be inserted."
            )

        query_asset_params = {"_filter_name": f'"{asset_name}"'}
        query_asset_request = self.get_endpoint(
            phantom_constants.ENDPOINT_ASSET, query_asset_params
        )

        query_asset_json = query_asset_request.json()
        num_assets_found = query_asset_json["count"]

        if num_assets_found >= 1:
            logging.info(
                'Found %d asset(s) with name "%s"', num_assets_found, asset_name
            )
            if overwrite:
                for asset_data in query_asset_json["data"]:
                    existing_asset_id = asset_data["id"]
                    self.delete_endpoint(
                        phantom_constants.ENDPOINT_ASSET, existing_asset_id
                    )
            else:
                return query_asset_json["data"][0]["id"]

        new_asset_request = self.post_endpoint(
            phantom_constants.ENDPOINT_ASSET, json_data=asset
        ).json()

        assert new_asset_request["success"] is True, (
            f"Failed to insert asset {asset_name}."
        )

        return new_asset_request["id"]

    def delete_asset(self, asset_id: int):
        """Delete an asset."""
        self.delete_endpoint(phantom_constants.ENDPOINT_ASSET, asset_id)

    def run_action(
        self, action: str, container_id: int, targets: list, name: str | None = None
    ) -> int:
        """Run an action."""
        if name is None:
            name = f"automation_test_run_{uuid.uuid4()}"

        data = {
            "action": action,
            "container_id": container_id,
            "name": name,
            "targets": targets,
        }

        run_action_response = self.post_endpoint(
            phantom_constants.ENDPOINT_RUN_ACTION, json_data=data
        ).json()

        return run_action_response["action_run_id"]

    def poll_now(
        self,
        asset_id: int,
        container_source_ids: str = "",
        max_containers: int = 1,
        max_artifacts: int = 10,
    ) -> dict:
        """Trigger the on poll action."""
        data = {
            "ingest_now": True,
            "container_source_ids": container_source_ids,
            "max_containers": max_containers,
            "max_artifacts": max_artifacts,
        }

        endpoint = f"{phantom_constants.ENDPOINT_ASSET}/{asset_id}"
        poll_now_message = self.post_endpoint(endpoint, json_data=data).json()
        logging.info("Poll now response %s", poll_now_message)

        return poll_now_message

    def enable_webhook(self, asset_id: int, webhook_config: dict | None = None) -> None:
        """Enable webhooks for an asset."""
        data = {"webhook": {**(webhook_config or {}), "enabled": True}}
        endpoint = f"{phantom_constants.ENDPOINT_ASSET}/{asset_id}"
        self.post_endpoint(endpoint, json_data=data)

    def get_webhook_base_url(self, asset_id: int) -> str:
        """Get the base URL for an asset webhook."""
        endpoint = f"{phantom_constants.ENDPOINT_ASSET}/{asset_id}"
        data = self.get_endpoint(endpoint).json()
        if not (webhook := data.get("webhook")):
            raise RuntimeError(f"Webhooks are not enabled on asset {asset_id}")
        host = urlparse(self.base_url).hostname
        port = webhook["webhook_port"]
        path = webhook["webhook_url"]
        return f"https://{host}:{port}{path}"

    def wait_for_action_completion(
        self,
        action_id: int,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> dict:
        """Wait for an action to complete and return its results."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_action_status(action_id)
            if status["status"] in [
                phantom_constants.STATUS_SUCCESS,
                phantom_constants.STATUS_FAILED,
            ]:
                return self.get_action_results(action_id)

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Action {action_id} did not complete within {timeout} seconds"
        )

    @asynccontextmanager
    async def attach_websocket(self):
        login_csrf_response = self.get("/login")
        csrf_token = login_csrf_response.cookies.get("csrftoken")
        login_response = self.post(
            "/login",
            data={
                "username": self.ph_user,
                "password": self.ph_pass,
                "csrfmiddlewaretoken": csrf_token,
            },
        )
        session_id = login_response.cookies.get("sessionid")

        websocket_server = urlparse(self.base_url).netloc
        ssl_context = ssl.create_default_context()
        if not self.verify_certs:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        async with websockets.connect(
            f"wss://{websocket_server}/websocket",
            additional_headers={"Cookie": f"sessionid={session_id}"},
            ssl=ssl_context,
        ) as w:
            yield w

    def get_automation_brokers(self, name: str | None = None) -> dict:
        """Query for automation brokers."""
        query_params = {}
        if name:
            query_params["_filter_name"] = f'"{name}"'
        return self.get_endpoint(
            phantom_constants.ENDPOINT_AUTOMATION_BROKER, query_params
        ).json()
