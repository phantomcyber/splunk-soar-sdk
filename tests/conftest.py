import io
import re
import struct
from pathlib import Path
from unittest import mock

import pytest
from extract_msg.ole_writer import OleWriter
from httpx import Response

from soar_sdk.abstract import SOARClient, SOARClientAuth
from soar_sdk.action_results import ActionOutput
from soar_sdk.actions_manager import ActionsManager
from soar_sdk.app import App
from soar_sdk.app_client import AppClient
from soar_sdk.asset import BaseAsset
from soar_sdk.asset_state import AssetState
from soar_sdk.compat import PythonVersion
from soar_sdk.input_spec import (
    AppConfig,
    InputSpecification,
    SoarAuth,
)
from soar_sdk.meta.dependencies import (
    UvDependency,
    UvLock,
    UvPackage,
    UvSource,
    UvSourceDistribution,
    UvWheel,
)
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse
from tests.stubs import SampleActionParams

PT_UNICODE = 0x001F
PT_BINARY = 0x0102
PT_LONG = 0x0003


def _make_prop_entry(prop_id, prop_type):
    tag = struct.pack("<HH", prop_type, prop_id)
    flags = struct.pack("<I", 0x00000006)
    value = struct.pack("<Q", 0)
    return tag + flags + value


def _add_string_prop(writer, prop_id, value, prefix=""):
    stream = f"{prefix}__substg1.0_{prop_id:04X}{PT_UNICODE:04X}"
    writer.addEntry(stream, value.encode("utf-16-le"))


def _add_binary_prop(writer, prop_id, value, prefix=""):
    stream = f"{prefix}__substg1.0_{prop_id:04X}{PT_BINARY:04X}"
    writer.addEntry(
        stream, value if isinstance(value, bytes) else value.encode("utf-8")
    )


@pytest.fixture
def msg_plaintext_only() -> bytes:
    """Build a minimal .msg file with only a plain text body (no HTML)."""
    writer = OleWriter()

    _add_string_prop(writer, 0x001A, "IPM.Note")
    _add_string_prop(writer, 0x0037, "Plaintext Only Subject")
    _add_string_prop(
        writer,
        0x1000,
        "This is the plain text body with a URL: https://example.com/plain-only",
    )
    _add_string_prop(writer, 0x0C1A, "Plain Sender")
    _add_string_prop(writer, 0x0C1F, "plain@example.com")

    props_header = b"\x00" * 32
    entries = b""
    for pid, pt in [
        (0x001A, PT_UNICODE),
        (0x0037, PT_UNICODE),
        (0x1000, PT_UNICODE),
        (0x0C1A, PT_UNICODE),
        (0x0C1F, PT_UNICODE),
    ]:
        entries += _make_prop_entry(pid, pt)
    writer.addEntry("__properties_version1.0", props_header + entries)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def msg_html_only() -> bytes:
    """Build a minimal .msg file with only an HTML body (no plain text)."""
    writer = OleWriter()

    _add_string_prop(writer, 0x001A, "IPM.Note")
    _add_string_prop(writer, 0x0037, "HTML Only Subject")
    _add_binary_prop(
        writer,
        0x1013,
        "<html><body><p>HTML body with "
        '<a href="https://html.example.com/html-only">a link</a>'
        "</p></body></html>",
    )
    _add_string_prop(writer, 0x0C1A, "HTML Sender")
    _add_string_prop(writer, 0x0C1F, "html@example.com")

    props_header = b"\x00" * 32
    entries = b""
    for pid, pt in [
        (0x001A, PT_UNICODE),
        (0x0037, PT_UNICODE),
        (0x1013, PT_BINARY),
        (0x0C1A, PT_UNICODE),
        (0x0C1F, PT_UNICODE),
    ]:
        entries += _make_prop_entry(pid, pt)
    writer.addEntry("__properties_version1.0", props_header + entries)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def msg_with_attachment() -> bytes:
    """Build a .msg file that includes a plain text body and one PDF attachment."""
    writer = OleWriter()

    _add_string_prop(writer, 0x001A, "IPM.Note")
    _add_string_prop(writer, 0x0037, "MSG With Attachment")
    _add_string_prop(writer, 0x1000, "Body text")
    _add_string_prop(writer, 0x0C1A, "Sender")
    _add_string_prop(writer, 0x0C1F, "sender@test.com")

    # Named properties streams (required by extract-msg for messages with attachments)
    writer.addEntry("__nameid_version1.0/__substg1.0_00020102", b"")
    writer.addEntry("__nameid_version1.0/__substg1.0_00030102", b"")
    writer.addEntry("__nameid_version1.0/__substg1.0_00040102", b"")

    # Attachment sub-storage
    att_prefix = "__attach_version1.0_#00000000/"
    _add_string_prop(writer, 0x3707, "document.pdf", prefix=att_prefix)
    _add_string_prop(writer, 0x370E, "application/pdf", prefix=att_prefix)
    _add_binary_prop(writer, 0x3701, b"%PDF-1.4 test content", prefix=att_prefix)

    # Attachment properties stream
    att_header = b"\x00" * 8
    att_entries = b""
    att_entries += _make_prop_entry(0x3707, PT_UNICODE)
    att_entries += _make_prop_entry(0x370E, PT_UNICODE)
    att_entries += _make_prop_entry(0x3701, PT_BINARY)
    # Attach Method (PT_LONG = fixed size, value goes inline)
    tag = struct.pack("<HH", PT_LONG, 0x3705)
    flags = struct.pack("<I", 0x00000006)
    value = struct.pack("<I", 1) + b"\x00" * 4  # ATTACH_BY_VALUE, padded to 8 bytes
    att_entries += tag + flags + value
    writer.addEntry(f"{att_prefix}__properties_version1.0", att_header + att_entries)

    # Root properties stream
    root_header = b"\x00" * 32
    root_entries = b""
    for pid in [0x001A, 0x0037, 0x1000, 0x0C1A, 0x0C1F]:
        root_entries += _make_prop_entry(pid, PT_UNICODE)
    writer.addEntry("__properties_version1.0", root_header + root_entries)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf55"


@pytest.fixture
def example_app() -> App:
    """Create an example app for testing."""
    app = App(
        name="example_app",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    )

    return app


@pytest.fixture
def example_provider(example_app: App) -> ActionsManager:
    """Create an example actions manager for testing."""
    return example_app.actions_manager


@pytest.fixture
def example_state(example_provider: ActionsManager) -> AssetState:
    """Create an example asset state manager for testing"""
    return AssetState(example_provider, "example", "1")


@pytest.fixture
def default_args():
    """Create default arguments for testing."""
    return mock.Mock(username="user", password="<PASSWORD>", input_test_json="{}")


@pytest.fixture
def simple_app() -> App:
    """Create a simple app instance for testing."""
    return App(
        name="simple_app",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    )


@pytest.fixture
def app_connector() -> AppClient:
    """Create an app connector for testing."""
    connector = AppClient()
    connector.client.headers.update({"X-CSRFToken": "fake-token"})
    return connector


@pytest.fixture
def app_with_action() -> App:
    """Create an app with a pre-configured 'test_action' for testing."""
    app = App(
        name="test_app",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
        python_version=[PythonVersion.PY_3_13],
    )

    @app.action(
        name="Test Action",
        identifier="test_action",
        description="Test action description",
        verbose="Test action verbose description",
    )
    def test_action(params: SampleActionParams) -> ActionOutput:
        """Test action description."""
        return ActionOutput()

    return app


@pytest.fixture
def app_with_asset_action() -> App:
    """Create an app with a pre-configured action that requires an asset."""
    app = App(
        name="test_app_with_asset",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    )

    @app.action(
        name="Test Action With Asset",
        identifier="test_action_with_asset",
        description="Test action that requires an asset",
    )
    def test_action_with_asset(params: SampleActionParams, asset: dict) -> ActionOutput:
        """Test action that requires an asset."""
        return ActionOutput()

    return app


@pytest.fixture
def app_with_simple_asset() -> App:
    """Create an app with a simple asset class for testing."""

    class Asset(BaseAsset):
        base_url: str

    return App(
        asset_cls=Asset,
        name="app_with_asset",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    )


@pytest.fixture
def app_with_asset_webhook(tmp_path: Path) -> App:
    """Create an app with a pre-configured action that requires an asset and webhook."""

    class Asset(BaseAsset):
        base_url: str

    app = App(
        asset_cls=Asset,
        name="test_app_with_asset_webhook",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    ).enable_webhooks()

    # Mock get_state_dir to use tmp_path instead of /opt/phantom
    app.actions_manager.get_state_dir = lambda: str(tmp_path)

    @app.webhook("test_webhook")
    def test_webhook_handler(request: WebhookRequest) -> WebhookResponse:
        """Test webhook handler."""
        return WebhookResponse.text_response("Webhook received!")

    return app


@pytest.fixture
def app_with_client_webhook(tmp_path: Path) -> App:
    """Create an app with a pre-configured action that requires an asset and webhook."""

    class Asset(BaseAsset):
        base_url: str

    app = App(
        asset_cls=Asset,
        name="test_app_with_asset_webhook",
        appid=APP_ID,
        app_type="sandbox",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_vendor="Splunk",
        product_name="Example App",
        publisher="Splunk",
    ).enable_webhooks()

    app.actions_manager.get_state_dir = lambda: str(tmp_path)

    @app.webhook("test_webhook")
    def test_webhook_handler(
        request: WebhookRequest, soar: SOARClient
    ) -> WebhookResponse:
        """Test webhook handler."""
        soar.get("rest/version")  # Example of using the SOAR client
        return WebhookResponse.text_response("Webhook received!")

    return app


@pytest.fixture
def simple_connector(simple_app: App) -> AppClient:
    """Create a simple app connector for testing."""
    return simple_app.soar_client


@pytest.fixture
def app_actions_manager(simple_app: App) -> AppClient:
    """Create an app actions manager for testing."""
    return simple_app.actions_manager


@pytest.fixture
def simple_action_input() -> InputSpecification:
    """Create a simple action input specification for testing."""
    return InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
    )


@pytest.fixture
def auth_action_input() -> InputSpecification:
    """Create an action input specification that uses SOAR authentication."""
    return InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
        soar_auth=SoarAuth(
            phantom_url="https://example.com",
            username="soar_local_admin",
            password="password",
        ),
    )


@pytest.fixture
def auth_token_input() -> InputSpecification:
    """Create an action input specification that uses SOAR authentication with a token."""
    return InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
        user_session_token="example_token",
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
def fake_sdist() -> UvSourceDistribution:
    """Use with sdist_resp_mock to test the source distribution download."""
    return UvSourceDistribution(
        url="https://files.pythonhosted.org/packages/splunk-soar-sdk-2.1.0.tar.gz",
        hash="sha256:63f9a259a7c84d0c3b0b32cae652365b03f0f926acdb894b51456005df74ae21",
        size=19,
    )


@pytest.fixture
def fake_uv_lockfile(fake_wheel) -> UvLock:
    """Create a fake UvLock object for testing."""
    return UvLock(
        package=[
            UvPackage(
                name="example-app",
                version="1.0.0",
                dependencies=[
                    UvDependency(name="fakepkg"),
                ],
                source=UvSource(registry="https://pypi.python.org/simple"),
            ),
            UvPackage(
                name="fakepkg",
                version="1.0.0",
                wheels=[fake_wheel],
                source=UvSource(registry="https://pypi.python.org/simple"),
            ),
        ]
    )


@pytest.fixture
@pytest.mark.respx(base_url="https://files.pythonhosted.org/packages")
def wheel_resp_mock(respx_mock):
    """Fixture that automatically mocks requests to download wheels. Useful for keeping tests for package builds fast and reliable."""
    # Create the mock route for wheel downloads
    mock_route = respx_mock.get(url__regex=r".+/.+\.whl")
    mock_route.respond(content=b"dummy wheel content")

    # Provide the mock route to the test so it can make assertions
    return mock_route


@pytest.fixture
@pytest.mark.respx(base_url="https://files.pythonhosted.org/packages")
def sdist_resp_mock(respx_mock):
    """Fixture that automatically mocks requests to download source distributions. Useful for keeping tests for package builds fast and reliable."""
    # Create the mock route for source distribution downloads
    mock_route = respx_mock.get(url__regex=r".+/.+\.tar\.gz")

    with Path("tests/test_assets/splunk-sdk-2.1.0.tar.gz").open("rb") as f:
        mock_route.respond(content=f.read())

    # Provide the mock route to the test so it can make assertions
    return mock_route


@pytest.fixture
@pytest.mark.respx(base_url="https://10.1.23.4/")
def mock_install_client(respx_mock):
    """Fixture to mock requests.Session."""
    # Mock the home page GET request for CSRF token
    respx_mock.get("/").respond(
        cookies={"csrftoken": "fake_csrf_token"}, status_code=200
    )

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
    """Create a dummy app tarball for testing."""
    tarball_path = tmp_path / "example.tgz"
    tarball_path.touch()
    return tarball_path


@pytest.fixture
def soar_client_auth() -> SOARClientAuth:
    """Create a SOARClientAuth object for testing."""
    return SOARClientAuth(
        base_url="https://10.34.5.6",
        username="soar_local_admin",
        password="password",
    )


@pytest.fixture
def soar_client_auth_token() -> SOARClientAuth:
    """Create a SOARClientAuth object for testing with a user session token."""
    return SOARClientAuth(
        base_url="https://10.34.5.6",
        user_session_token="example_token",
    )


@pytest.fixture
@pytest.mark.respx
def mock_post_artifact(respx_mock):
    """Fixture to mock POST requests to create artifacts."""
    mock_route = respx_mock.post(re.compile(r".*/rest/artifact/?$")).mock(
        return_value=Response(201, json={"message": "Mocked artifact created", "id": 1})
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_get_any_soar_call(respx_mock):
    """Fixture to mock GET requests to any SOAR endpoint."""
    mock_route = respx_mock.get(re.compile(r".*")).mock(
        return_value=Response(
            200,
            json={"message": "Mocked GET response"},
            headers={"Set-Cookie": "csrftoken=mocked_csrf_token; Path=/; HttpOnly"},
        )
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_put_any_call(respx_mock):
    """Fixture to mock PUT requests to any SOAR endpoint."""
    mock_route = respx_mock.put(re.compile(r".*")).mock(
        return_value=Response(200, json={"message": "Mocked PUT response"})
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_post_any_soar_call(respx_mock):
    """Fixture to mock POST requests to any SOAR endpoint."""
    mock_route = respx_mock.post(re.compile(r".*")).mock(
        return_value=Response(
            200,
            json={"message": "Mocked POST response"},
            headers={"Set-Cookie": "sessionid=mocked_session_id; Path=/; HttpOnly"},
        )
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_delete_any_soar_call(respx_mock):
    """Fixture to mock DELETE requests to any SOAR endpoint."""
    mock_route = respx_mock.delete(re.compile(r".*")).mock(
        return_value=Response(
            200,
            json={"message": "Mocked Deleted response"},
            headers={"Set-Cookie": "sessionid=mocked_session_id; Path=/; HttpOnly"},
        )
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_post_container(respx_mock):
    """Fixture to mock POST requests to create containers."""
    mock_route = respx_mock.post(re.compile(r".*/rest/container/?$")).mock(
        return_value=Response(
            201, json={"message": "Mocked container created", "id": 1}
        )
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_post_vault(respx_mock):
    """Fixture to mock POST requests to add attachments to vault."""
    mock_route = respx_mock.post(re.compile(r".*/rest/container_attachment/?$")).mock(
        return_value=Response(201, json={"message": "Attachment added", "id": 1})
    )
    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_get_vault(respx_mock):
    """Fixture to mock GET requests to retrieve attachments from vault."""
    mock_route = respx_mock.get(re.compile(r".*/rest/container_attachment.*")).mock(
        return_value=Response(
            201,
            json={
                "message": "Retrieved attachment",
                "id": 1,
                "num_pages": 1,
                "data": [
                    {
                        "id": 1,
                        "created_via": "manual upload",
                        "container": "test_1",
                        "task": "",
                        "create_time": "3 minutes ago",
                        "name": "test.txt",
                        "user": "Phantom Admin",
                        "vault_document": 214,
                        "mime_type": "text/plain",
                        "es_attachment_id": None,
                        "hash": "f1245088566efd873af926569ab5788a8ae280d0",
                        "vault_id": "f1245088566efd873af926569ab5788a8ae280d0",
                        "size": 237612,
                        "path": "/opt/phantom/vault/f1/24/f1245088566efd873af926569ab5788a8ae280d0",
                        "metadata": {
                            "sha1": "f1245088566efd873af926569ab5788a8ae280d0",
                            "size": 237612,
                            "sha256": "d7116a30339ad6eca05b6abd9f9d9d0002b23704fcf8fc85fa209d0947541b4f",
                            "contains": ["vault id"],
                        },
                        "aka": ["test.txt"],
                        "container_id": 1,
                        "contains": ["vault id"],
                    }
                ],
            },
        )
    )

    return mock_route


@pytest.fixture
@pytest.mark.respx
def mock_delete_vault(respx_mock):
    """Fixture to mock DELETE requests to remove attachments from vault."""
    mock_route = respx_mock.delete(re.compile(r".*/rest/container_attachment.*")).mock(
        return_value=Response(200, json={"message": "Attachment deleted", "id": 1})
    )

    return mock_route
