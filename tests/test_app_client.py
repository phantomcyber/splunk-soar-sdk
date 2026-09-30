import ssl
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from soar_sdk.abstract import SOARClient, SOARClientAuth
from soar_sdk.action_results import ActionOutput
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault
from soar_sdk.app_client import AppClient


class ConcreteSOARClient(SOARClient[ActionOutput]):
    """Minimal concrete implementation for testing SOARClient base methods."""

    def __init__(self, base_url: str = "https://localhost:9999") -> None:
        self._client = httpx.Client(base_url=base_url, verify=False)
        self._artifact = Artifact(soar_client=self)
        self._container = Container(soar_client=self)
        self._vault = Vault(soar_client=self)

    @property
    def client(self) -> httpx.Client:
        return self._client

    @property
    def vault(self) -> Vault:
        return self._vault

    @property
    def artifact(self) -> Artifact:
        return self._artifact

    @property
    def container(self) -> Container:
        return self._container

    def get_executing_container_id(self) -> int:
        return 0

    def get_asset_id(self) -> str:
        return ""

    def update_client(
        self, soar_auth: SOARClientAuth, asset_id: str, container_id: int = 0
    ) -> None:
        pass

    def set_summary(self, summary: ActionOutput) -> None:
        pass

    def set_message(self, message: str) -> None:
        pass

    def get_summary(self) -> ActionOutput | None:
        return None

    def get_message(self) -> str:
        return ""


@pytest.fixture
def soar_client() -> ConcreteSOARClient:
    return ConcreteSOARClient()


@pytest.mark.parametrize("verify_ssl", [True, False])
def test_app_client_uses_platform_tls_setting(verify_ssl: bool):
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=verify_ssl),
        patch("soar_sdk.app_client.httpx.Client") as mock_client,
        patch.object(
            AppClient,
            "get_soar_base_url",
            return_value="https://localhost:9999",
        ),
    ):
        AppClient()

    mock_client.assert_called_once_with(
        base_url="https://localhost:9999",
        verify=verify_ssl,
    )


@pytest.mark.parametrize("verify_ssl", [True, False])
def test_authenticate_soar_client_uses_platform_tls_setting(
    simple_connector: AppClient,
    verify_ssl: bool,
):
    auth = SOARClientAuth(
        base_url="https://10.34.5.6",
        broker_ph_auth_token="broker-token",
    )

    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=verify_ssl),
        patch("soar_sdk.app_client.httpx.Client") as mock_client,
        patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True),
    ):
        simple_connector.authenticate_soar_client(auth)

    mock_client.assert_called_once_with(
        base_url="https://10.34.5.6",
        verify=verify_ssl,
    )


@pytest.fixture
def loopback_https_server(tmp_path):
    """Serve HTTPS on loopback with a certificate that has only a DNS SAN."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "soar.example.com")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("soar.example.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header(
                    "Location", f"https://localhost:{server.server_port}/ok"
                )
            else:
                self.send_response(200)
                self.send_header("Set-Cookie", "csrftoken=test-csrf; Path=/")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    alternate_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    alternate_server.socket = context.wrap_socket(
        alternate_server.socket, server_side=True
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    alternate_thread = Thread(target=alternate_server.serve_forever, daemon=True)
    thread.start()
    alternate_thread.start()
    try:
        yield (
            f"https://127.0.0.1:{server.server_port}",
            f"https://127.0.0.1:{alternate_server.server_port}",
            cert_path,
        )
    finally:
        server.shutdown()
        alternate_server.shutdown()
        thread.join()
        alternate_thread.join()
        server.server_close()
        alternate_server.server_close()


def test_native_loopback_skips_certificate_check_only_for_loopback(
    loopback_https_server, monkeypatch
):
    base_url, alternate_url, cert_path = loopback_https_server
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "localhost")
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_onprem_broker_install", return_value=False),
        patch.object(AppClient, "get_soar_base_url", return_value=base_url),
    ):
        app_client = AppClient()
        try:
            assert app_client.client.get("/ok").status_code == 200
            with pytest.raises(httpx.ConnectError, match="IP address mismatch"):
                app_client.client.get(alternate_url)
            with pytest.raises(httpx.ConnectError, match="Hostname mismatch"):
                app_client.client.get("/redirect", follow_redirects=True)

            app_client.authenticate_soar_client(
                SOARClientAuth(base_url=base_url, user_session_token="session")
            )
            assert app_client.csrf_token == "test-csrf"
        finally:
            app_client.client.close()


def test_broker_loopback_keeps_certificate_verification(
    loopback_https_server, monkeypatch
):
    base_url, _, cert_path = loopback_https_server
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True),
        patch.object(AppClient, "get_soar_base_url", return_value=base_url),
    ):
        app_client = AppClient()
        try:
            with pytest.raises(httpx.ConnectError, match="IP address mismatch"):
                app_client.client.get("/ok")
        finally:
            app_client.client.close()


@respx.mock
def test_soar_client_get(soar_client: ConcreteSOARClient):
    route = respx.get("https://localhost:9999/rest/test").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    response = soar_client.get("/rest/test")
    assert route.called
    assert response.json() == {"ok": True}


@respx.mock
def test_soar_client_get_raises_on_error(soar_client: ConcreteSOARClient):
    respx.get("https://localhost:9999/rest/test").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        soar_client.get("/rest/test")


@respx.mock
def test_soar_client_post(soar_client: ConcreteSOARClient):
    route = respx.post("https://localhost:9999/rest/data").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    response = soar_client.post("/rest/data", json={"name": "test"})
    assert route.called
    assert response.json() == {"id": 1}
    request = route.calls[0].request
    assert "Referer" in request.headers


@respx.mock
def test_soar_client_post_raises_on_error(soar_client: ConcreteSOARClient):
    respx.post("https://localhost:9999/rest/data").mock(
        return_value=httpx.Response(403)
    )
    with pytest.raises(httpx.HTTPStatusError):
        soar_client.post("/rest/data", json={"name": "test"})


@respx.mock
def test_soar_client_put(soar_client: ConcreteSOARClient):
    route = respx.put("https://localhost:9999/rest/data/1").mock(
        return_value=httpx.Response(200, json={"updated": True})
    )
    response = soar_client.put("/rest/data/1", json={"name": "updated"})
    assert route.called
    assert response.json() == {"updated": True}
    request = route.calls[0].request
    assert "Referer" in request.headers


@respx.mock
def test_soar_client_put_raises_on_error(soar_client: ConcreteSOARClient):
    respx.put("https://localhost:9999/rest/data/1").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(httpx.HTTPStatusError):
        soar_client.put("/rest/data/1", json={"name": "updated"})


def test_update_client(
    simple_connector: AppClient,
    soar_client_auth: SOARClientAuth,
    mock_get_any_soar_call,
    mock_post_any_soar_call,
):
    simple_connector.update_client(soar_client_auth, 1)
    assert mock_get_any_soar_call.call_count == 1
    request = mock_get_any_soar_call.calls[0].request
    assert request.url == "https://10.34.5.6/login"
    assert simple_connector.client.headers["X-CSRFToken"] == "mocked_csrf_token"

    assert mock_post_any_soar_call.call_count == 1
    post_request = mock_post_any_soar_call.calls[0].request
    assert post_request.url == "https://10.34.5.6/login"

    assert (
        simple_connector.client.headers["Cookie"]
        == "sessionid=mocked_session_id;csrftoken=mocked_csrf_token"
    )


def test_authenticate_soar_client_on_platform(
    simple_connector: AppClient,
    soar_client_auth_token: SOARClientAuth,
    mock_get_any_soar_call,
):
    simple_connector.authenticate_soar_client(soar_client_auth_token)
    assert mock_get_any_soar_call.call_count == 1


def test_get_executing_container_id(simple_connector: AppClient):
    assert simple_connector.get_executing_container_id() == 0


def test_get_asset_id(simple_connector: AppClient):
    assert simple_connector.get_asset_id() == ""


@patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True)
def test_authenticate_skips_login_on_broker(mock_broker, simple_connector: AppClient):
    """Test that broker auth with a token skips session-based login."""
    auth = SOARClientAuth(
        base_url="https://10.34.5.6",
        broker_ph_auth_token="broker-token",
        user_hash_key="hash-key",
    )
    simple_connector.authenticate_soar_client(auth)
    assert simple_connector._broker_ph_auth_token == "broker-token"


@patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True)
@respx.mock
def test_prepare_broker_request(mock_broker, simple_connector: AppClient):
    """Test that broker requests are routed through api_proxy with auth headers."""
    simple_connector._broker_ph_auth_token = "broker-token"
    simple_connector._user_hash_key = "hash-key"

    route = respx.get("https://localhost:9999/rest/broker/api_proxy/rest/version").mock(
        return_value=httpx.Response(200, json={"version": "6.4.1"})
    )
    response = simple_connector.get("/rest/version")

    assert route.called
    request = route.calls[0].request
    assert request.headers["ph-auth-token"] == "broker-token"
    assert request.headers["PsaasImpersonationToken"] == "hash-key"
    assert response.json() == {"version": "6.4.1"}


@patch("soar_sdk.app_client.is_onprem_broker_rpc_install", return_value=True)
@patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True)
@respx.mock
def test_prepare_broker_request_rpc(mock_broker, mock_rpc, simple_connector: AppClient):
    """Test that RPC broker requests use a Bearer token instead of ph-auth-token."""
    simple_connector._broker_ph_auth_token = "broker-token"
    simple_connector._user_hash_key = "hash-key"

    route = respx.get("https://localhost:9999/rest/broker/api_proxy/rest/version").mock(
        return_value=httpx.Response(200, json={"version": "6.4.1"})
    )
    response = simple_connector.get("/rest/version")

    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer broker-token"
    assert request.headers["PsaasImpersonationToken"] == "hash-key"
    assert "ph-auth-token" not in request.headers
    assert response.json() == {"version": "6.4.1"}


@patch("soar_sdk.app_client.is_onprem_broker_install", return_value=True)
@respx.mock
def test_prepare_broker_request_adds_leading_slash(
    mock_broker, simple_connector: AppClient
):
    """Test that broker request preparation adds a leading slash when missing."""
    simple_connector._broker_ph_auth_token = "broker-token"
    simple_connector._user_hash_key = "hash-key"

    route = respx.get("https://localhost:9999/rest/broker/api_proxy/rest/version").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    simple_connector.get("rest/version")

    assert route.called
