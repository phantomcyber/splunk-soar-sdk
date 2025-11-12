import os
from pathlib import Path

import pytest


class AppOnStackClient:
    def __init__(
        self, host, port, username, password, broker_id, app, asset, verify_cert=True
    ):
        pass

    def install_app(self):
        pass

    def create_asset(self):
        pass

    def run_test_connectivity(self):
        pass

    def run_action(self, action_name, params):
        pass

    def run_poll(self, params):
        pass

    def enable_webhook(self, params):
        pass

    @property
    def webhook_base_url(self):
        return ""

    def cleanup(self):
        pass


@pytest.fixture(scope="session")
def example_app_installed():
    client = AppOnStackClient(
        os.environ["PH_HOST"],
        os.environ["PH_PORT"],
        os.environ["PH_USER"],
        os.environ["PH_PASS"],
        os.environ.get("PH_BROKER_ID"),
        Path.cwd() / "tests" / "example_app",
        {"name": "test_asset"},
    )

    client.install_app()
    client.create_asset()
    yield client

    client.cleanup()
