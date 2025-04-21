import json
from unittest import mock

import pytest

from soar_sdk.actions_provider import ActionsProvider
from soar_sdk.app import App
from soar_sdk.app_runner import AppRunner
from soar_sdk.connector import AppConnector


@pytest.fixture
def example_app() -> App:
    app = App()
    app.actions_provider.soar_client._load_app_json = mock.Mock(return_value=True)
    app.actions_provider.soar_client.get_state_dir = mock.Mock(return_value="/tmp/")
    app.actions_provider.soar_client._load_app_json = mock.Mock(return_value=True)

    with open("tests/example_app/app.json") as app_json:
        app.actions_provider.soar_client._BaseConnector__app_json = json.load(app_json)

    return app


@pytest.fixture
def example_provider(example_app):
    return example_app.actions_provider


@pytest.fixture
def default_args():
    return mock.Mock(username="user", password="<PASSWORD>", input_test_json="{}")


@pytest.fixture
def simple_app() -> App:
    return App()


@pytest.fixture
def simple_provider(simple_app) -> ActionsProvider:
    return simple_app.actions_provider


@pytest.fixture
def simple_connector(simple_app) -> AppConnector:
    return AppConnector(simple_app.actions_provider)


@pytest.fixture
def app_connector(simple_app) -> AppConnector:
    return AppConnector(simple_app.actions_provider)


@pytest.fixture
def simple_runner(simple_app, default_args) -> AppRunner:
    with mock.patch("argparse.ArgumentParser.parse_args", default_args):
        return AppRunner(simple_app)


@pytest.fixture
def simple_action_input() -> str:
    return json.dumps(
        {
            "asset_id": 1,
            "config": {},
            "parameters": [{}],
            "identifier": "test_action",
        }
    )
