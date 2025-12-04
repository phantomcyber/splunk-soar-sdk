from __future__ import annotations

import json
import logging
import time
from asyncio import timeout
from contextlib import suppress
from dataclasses import dataclass

from .phantom_constants import ACTION_TEST_CONNECTIVITY, STATUS_SUCCESS
from .phantom_instance import PhantomInstance

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    success: bool
    message: str
    data: dict | None = None


class AppOnStackClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        app_name: str,
        app_vendor: str,
        asset_config: dict,
        verify_cert: bool = False,
        automation_broker_name: str | None = None,
    ):
        self.host = host
        self.app_name = app_name
        self.app_vendor = app_vendor
        self.asset_config = asset_config
        self.automation_broker_name = automation_broker_name

        base_url = f"https://{host}"
        self.phantom = PhantomInstance(
            base_url=base_url,
            ph_user=username,
            ph_pass=password,
            verify_certs=verify_cert,
        )

        self.app_info: dict | None = None
        self.asset_id: int | None = None
        self.container_id: int | None = None

    def setup_app(self) -> None:
        app_info_result = self.phantom.get_app_info(
            name=self.app_name, vendor=self.app_vendor
        )
        if app_info_result["count"] == 0:
            raise RuntimeError(
                f"App '{self.app_name}' not found. Make sure it's installed on the instance."
            )
        self.app_info = app_info_result["data"][0]

        asset_name = f"{self.app_name}_integration_test_asset_{int(time.time())}"
        asset_data = {
            "name": asset_name,
            "product_vendor": self.app_info["product_vendor"],
            "product_name": self.app_info["product_name"],
            "app_version": self.app_info["app_version"],
            "configuration": self.asset_config,
        }

        if self.automation_broker_name:
            ab_results = self.phantom.get_automation_brokers(
                name=self.automation_broker_name
            )
            if ab_results["count"] == 0:
                logger.warning(
                    f"Automation broker '{self.automation_broker_name}' not found. "
                    "Asset will be created without an automation broker."
                )
            else:
                ab_id = ab_results["data"][0]["id"]
                asset_data["automation_broker_id"] = ab_id
                logger.info(
                    f"Setting automation broker '{self.automation_broker_name}' "
                    f"(ID: {ab_id}) for asset '{asset_name}'"
                )

        self.asset_id = self.phantom.insert_asset(asset_data, overwrite=True)

        label = "integration_test"
        with suppress(Exception):
            self.phantom.create_label(label)

        self.container_id = self.phantom.create_container(
            container_name=f"Integration Test Container - {self.app_name}",
            label=label,
            tags=["integration_test", "sdk"],
        )

    def run_test_connectivity(self) -> ActionResult:
        if not self.app_info or not self.asset_id or not self.container_id:
            raise RuntimeError("App not set up. Call setup_app() first.")

        targets = [{"app_id": self.app_info["id"], "assets": [self.asset_id]}]

        action_id = self.phantom.run_action(
            action=ACTION_TEST_CONNECTIVITY,
            container_id=self.container_id,
            targets=targets,
            name="integration_test_connectivity",
        )

        results = self.phantom.wait_for_action_completion(action_id, timeout=300)
        if not results or "data" not in results or len(results["data"]) == 0:
            return ActionResult(
                success=False, message="No action runs in results", data=results
            )

        action_run = results["data"][0]
        if "result_data" not in action_run or len(action_run["result_data"]) == 0:
            return ActionResult(
                success=False, message="No result_data in action run", data=results
            )

        action_result = action_run["result_data"][0]
        success = action_result.get("status") == STATUS_SUCCESS
        message = action_result.get("message", "Unknown result")

        return ActionResult(success=success, message=message, data=action_result)

    def run_action(self, action_name: str, params: dict) -> ActionResult:
        if not self.app_info or not self.asset_id or not self.container_id:
            raise RuntimeError("App not set up. Call setup_app() first.")

        targets = [
            {
                "app_id": self.app_info["id"],
                "assets": [self.asset_id],
                "parameters": [params],
            }
        ]

        action_id = self.phantom.run_action(
            action=action_name,
            container_id=self.container_id,
            targets=targets,
            name=f"integration_test_{action_name}",
        )

        results = self.phantom.wait_for_action_completion(action_id, timeout=300)
        if not results or "data" not in results or len(results["data"]) == 0:
            return ActionResult(
                success=False, message="No action runs in results", data=results
            )

        action_run = results["data"][0]
        if "result_data" not in action_run or len(action_run["result_data"]) == 0:
            return ActionResult(
                success=False, message="No result_data in action run", data=results
            )

        action_result = action_run["result_data"][0]
        success = action_result.get("status") == STATUS_SUCCESS
        message = action_result.get("message", "Unknown result")

        return ActionResult(success=success, message=message, data=action_result)

    async def run_poll(
        self,
        container_source_ids: str = "",
        max_containers: int = 1,
        max_artifacts: int = 10,
    ) -> ActionResult:
        if not self.app_info or not self.asset_id:
            raise RuntimeError("App not set up. Call setup_app() first.")

        async with self.phantom.attach_websocket() as websocket, timeout(3):
            await websocket.send(
                json.dumps(
                    {
                        "asset_id": self.asset_id,
                        "register": True,
                        "referer": f"/apps/{self.app_info['id']}/asset/{self.asset_id}/",
                        "id": json.dumps({"asset_id": self.asset_id}),
                    }
                )
            )

            result = self.phantom.poll_now(
                asset_id=self.asset_id,
                container_source_ids=container_source_ids,
                max_containers=max_containers,
                max_artifacts=max_artifacts,
            )

            if not result.get("received"):
                raise RuntimeError(f"Starting polling failed: {result}")
            subscription_id = result["poll_id"]

            async for messages_json in websocket:
                messages: list[dict] = json.loads(messages_json)
                for message in messages:
                    if message.get("subscription_id") != subscription_id:
                        continue
                    match message.get("status"):
                        case "progress":
                            continue
                        case "success":
                            await websocket.send(
                                json.dumps(
                                    {
                                        "asset_id": self.asset_id,
                                        "unregister": True,
                                        "referer": f"/apps/{self.app_info['id']}/asset/{self.asset_id}/",
                                    }
                                )
                            )
                            return ActionResult(success=True, message=message)

    def enable_webhook(self, webhook_config: dict | None = None) -> None:
        if not self.app_info or not self.asset_id:
            raise RuntimeError("App not set up. Call setup_app() first.")
        self.phantom.enable_webhook(self.asset_id, webhook_config)

    @property
    def webhook_base_url(self) -> str:
        return self.phantom.get_webhook_base_url(self.asset_id)

    def get_ingested_containers(self) -> list[dict]:
        return self.phantom.find_containers_from_asset(self.asset_id)

    def delete_ingested_containers(self) -> None:
        for container in self.get_ingested_containers():
            self.phantom.delete_container(container["id"])

    def cleanup(self) -> None:
        if self.container_id:
            try:
                self.phantom.delete_container(self.container_id)
            except Exception as e:
                logger.warning(f"Failed to delete container {self.container_id}: {e}")

        if self.asset_id:
            try:
                self.phantom.delete_asset(self.asset_id)
            except Exception as e:
                logger.warning(f"Failed to delete asset {self.asset_id}: {e}")

        self.delete_ingested_containers()
