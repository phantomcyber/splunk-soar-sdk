import httpx
import pytest
import respx

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
