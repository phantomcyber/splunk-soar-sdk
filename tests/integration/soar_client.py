from __future__ import annotations

import logging
import time
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
    ):
        self.host = host
        self.app_name = app_name
        self.app_vendor = app_vendor
        self.asset_config = asset_config

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

    def run_poll(self, params: dict | None = None) -> ActionResult:
        if not self.app_info or not self.asset_id:
            raise RuntimeError("App not set up. Call setup_app() first.")

        result = self.phantom.poll_now(
            app_id=self.app_info["id"],
            asset_id=self.asset_id,
            container_id=self.container_id,
        )

        success = result.get("success", False)
        message = result.get("message", "Poll completed")

        return ActionResult(success=success, message=message, data=result)

    def enable_webhook(self, webhook_config: dict | None = None) -> ActionResult:
        if not self.app_info or not self.asset_id:
            raise RuntimeError("App not set up. Call setup_app() first.")

        return ActionResult(
            success=True,
            message="Webhook support placeholder",
            data={"webhook_url": self.webhook_base_url},
        )

    @property
    def webhook_base_url(self) -> str:
        if not self.app_info or not self.asset_id:
            return ""
        return f"https://{self.host}/rest/handler/{self.app_name}/{self.asset_id}"

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
