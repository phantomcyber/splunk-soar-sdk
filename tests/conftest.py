import json
from unittest import mock

import pytest

from soar_sdk.actions_provider import ActionsProvider
from soar_sdk.app import App
from soar_sdk.asset import BaseAsset
from soar_sdk.connector import AppConnector
from soar_sdk.input_spec import AppConfig, InputSpecification
from soar_sdk.action_results import ActionOutput
from soar_sdk.meta.dependencies import UvWheel
from tests.stubs import SampleActionParams
from pathlib import Path


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
def app_with_action() -> App:
    """Create an app with a pre-configured 'test_action' for testing."""
    app = App()

    @app.action(
        name="Test Action",
        identifier="test_action",
        description="Test action description",
        verbose="Test action verbose description",
    )
    def test_action(params: SampleActionParams) -> ActionOutput:
        """Test action description"""
        return ActionOutput()

    return app


@pytest.fixture
def app_with_asset_action() -> App:
    """Create an app with a pre-configured action that requires an asset."""
    app = App()

    @app.action(
        name="Test Action With Asset",
        identifier="test_action_with_asset",
        description="Test action that requires an asset",
    )
    def test_action_with_asset(params: SampleActionParams, asset: dict) -> ActionOutput:
        """Test action that requires an asset"""
        return ActionOutput()

    return app


@pytest.fixture
def app_with_simple_asset() -> App:
    class Asset(BaseAsset):
        base_url: str

    return App(asset_cls=Asset)


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
def simple_action_input() -> InputSpecification:
    return InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
    )


@pytest.fixture
def fake_wheel() -> UvWheel:
    """Use with wheel_resp_mock to test the wheel download."""
    return UvWheel(
        url="https://files.pythonhosted.org/packages/fakepkg-1.0.0-py3-none-any.whl",
        hash="sha256:3c7937d9ce42399210771a60640e3b35e35644b376f854a8da1de8b99fa02fe5",
        size=19,
    )


@pytest.fixture
@pytest.mark.respx(base_url="https://files.pythonhosted.org/packages")
def wheel_resp_mock(respx_mock):
    """
    Fixture that automatically mocks requests to download wheels.
    Useful for keeping tests for package builds fast and reliable.
    """
    # Create the mock route for wheel downloads
    mock_route = respx_mock.get(url__regex=r".+/.+\.whl")
    mock_route.respond(content=b"dummy wheel content")

    # Provide the mock route to the test so it can make assertions
    return mock_route


@pytest.fixture
@pytest.mark.respx(base_url="https://10.1.23.4/")
def mock_install_client(respx_mock):
    """Fixture to mock requests.Session."""
    respx_mock.get("login").respond(
        cookies={"csrftoken": "mocked_csrf_token"}, status_code=200
    )

    respx_mock.post("login").respond(
        cookies={"csrftoken": "fake_csrf_token", "sessionid": "fake_session_id"},
        status_code=200,
    )

    # Mock the POST request for app upload at /app_install
    respx_mock.post("app_install").respond(json={"status": "success"}, status_code=201)
    return respx_mock


@pytest.fixture
def app_tarball(tmp_path: Path) -> Path:
    tarball_path = tmp_path / "example.tgz"
    tarball_path.touch()
    return tarball_path
