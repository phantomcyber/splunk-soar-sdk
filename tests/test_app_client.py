import ssl
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingTCPServer
from threading import Thread
from unittest.mock import patch

import httpx
import pytest
import respx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from soar_sdk.abstract import SOARClient, SOARClientAuth
from soar_sdk.action_results import ActionOutput
from soar_sdk.apis.artifact import Artifact
from soar_sdk.apis.container import Container
from soar_sdk.apis.vault import Vault
from soar_sdk.app_client import AppClient, _create_soar_client


class _TLSHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Set-Cookie", "csrftoken=test-csrf")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


class _TLSServer(ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, context: ssl.SSLContext):
        self.context = context
        super().__init__(("127.0.0.1", 0), _TLSHandler)

    def get_request(self):
        connection, address = super().get_request()
        return self.context.wrap_socket(connection, server_side=True), address


@pytest.fixture
def loopback_tls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SOAR test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    def make_leaf(filename: str) -> tuple[Path, Path]:
        name = "soar.example.test"
        leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca_name)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=True
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        cert_path = tmp_path / f"{filename}.pem"
        key_path = tmp_path / f"{filename}.key"
        cert_path.write_bytes(
            leaf_cert.public_bytes(serialization.Encoding.PEM)
            + ca_cert.public_bytes(serialization.Encoding.PEM)
        )
        key_path.write_bytes(
            leaf_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        return cert_path, key_path

    nginx_cert, nginx_key = make_leaf("nginx")
    other_cert, _ = make_leaf("other")
    ca_path = tmp_path / "ca.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(nginx_cert, nginx_key)
    server = _TLSServer(context)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield (
        f"https://127.0.0.1:{server.server_address[1]}",
        nginx_cert,
        other_cert,
        ca_path,
    )
    server.shutdown()
    thread.join()
    server.server_close()


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


def test_cloud_loopback_pins_nginx_leaf(loopback_tls: tuple[str, Path, Path, Path]):
    base_url, nginx_cert, other_cert, ca_path = loopback_tls
    ca_context = ssl.create_default_context(cafile=str(ca_path))
    with (
        httpx.Client(verify=ca_context) as client,
        pytest.raises(httpx.ConnectError, match="IP address mismatch"),
    ):
        client.get(base_url)

    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_cloud_install", return_value=True),
        patch("soar_sdk.app_client.NGINX_CERT", str(nginx_cert)),
        _create_soar_client(base_url) as client,
    ):
        assert client.get("/rest/version").status_code == 200

    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_cloud_install", return_value=True),
        patch("soar_sdk.app_client.NGINX_CERT", str(other_cert)),
        _create_soar_client(base_url) as client,
        pytest.raises(httpx.ConnectError),
    ):
        client.get("/rest/version")


def test_cloud_loopback_login_uses_pinned_leaf(
    loopback_tls: tuple[str, Path, Path, Path],
):
    base_url, nginx_cert, _, _ = loopback_tls
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_cloud_install", return_value=True),
        patch("soar_sdk.app_client.NGINX_CERT", str(nginx_cert)),
        patch.object(AppClient, "get_soar_base_url", return_value=base_url),
    ):
        connector = AppClient()
        connector.authenticate_soar_client(
            SOARClientAuth(base_url=base_url, user_session_token="test-session")
        )

    assert connector.csrf_token == "test-csrf"
    assert "sessionid=test-session" in connector.client.headers["Cookie"]
    connector.client.close()


@pytest.mark.parametrize(
    ("base_url", "verify_ssl", "is_cloud"),
    [
        ("https://127.0.0.1:443", False, True),
        ("https://127.0.0.1:443", True, False),
        ("https://soar.example.test", True, True),
        ("https://10.34.5.6", True, True),
        ("http://127.0.0.1:80", True, True),
    ],
)
def test_soar_client_uses_default_transport_outside_verified_cloud_loopback(
    base_url: str, verify_ssl: bool, is_cloud: bool
):
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=verify_ssl),
        patch("soar_sdk.app_client.is_cloud_install", return_value=is_cloud),
        patch("soar_sdk.app_client.NGINX_CERT", "/missing/nginx-cert.pem"),
        patch("soar_sdk.app_client.httpx.Client") as mock_client,
    ):
        _create_soar_client(base_url)

    mock_client.assert_called_once_with(base_url=base_url, verify=verify_ssl)


def test_cloud_loopback_rejects_malformed_nginx_pem(tmp_path: Path):
    cert_path = tmp_path / "nginx-cert.pem"
    cert_path.write_text("not a PEM certificate", encoding="ascii")
    with (
        patch("soar_sdk.app_client.get_verify_ssl_setting", return_value=True),
        patch("soar_sdk.app_client.is_cloud_install", return_value=True),
        patch("soar_sdk.app_client.NGINX_CERT", str(cert_path)),
        pytest.raises(ValueError, match="does not contain a PEM certificate"),
    ):
        _create_soar_client("https://127.0.0.1:443")


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
