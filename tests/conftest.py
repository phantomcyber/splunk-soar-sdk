import json

# import sys
# import types
# from pprint import pprint
from unittest import mock

import pytest

from example_app.app import app
from soar_sdk.app import App
from soar_sdk.app_runner import AppRunner
from soar_sdk.connector import AppConnector

# FIXME: we need to provide proper mocks for the phantom library
#
# app_module = __import__("tests.mocks.phantom.app", fromlist=["tests.mocks.phantom"])
# action_result_module = __import__("tests.mocks.phantom.action_result", fromlist=["tests.mocks.phantom"])
# base_connector_module = __import__("tests.mocks.phantom.base_connector", fromlist=["tests.mocks.phantom.base_connector"])
# sys.modules["phantom.action_result"] = action_result_module
# sys.modules["phantom.app"] = app_module
# sys.modules["phantom.base_connector"] = base_connector_module
# sys.modules["phantom"] = types.ModuleType("phantom")
#


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
