import json
from unittest import mock

import pytest

from example_app.app import app
from soar_sdk.app import App
from soar_sdk.app_runner import AppRunner
from soar_sdk.connector import AppConnector


@pytest.fixture
def example_app():
    app.connector._load_app_json = mock.Mock(return_value=True)
    app.connector.get_state_dir = mock.Mock(return_value="/tmp/")
    app.connector._load_app_json = mock.Mock(return_value=True)

    with open("example_app/app.json") as app_json:
        app.connector._BaseConnector__app_json = json.load(app_json)

    return app


@pytest.fixture
def default_args():
    return mock.Mock(username="user", password="<PASSWORD>", input_test_json="{}")


@pytest.fixture
def simple_app():
    return App()


@pytest.fixture
def simple_connector(simple_app):
    return AppConnector(simple_app)


@pytest.fixture
def simple_runner(simple_app, default_args):
    with mock.patch("argparse.ArgumentParser.parse_args", default_args):
        return AppRunner(simple_app)


@pytest.fixture
def simple_action_input():
    return json.dumps(
        {
            "asset_id": 1,
            "config": {},
            "parameters": [],
            "identifier": "test_connectivity",
        }
    )
