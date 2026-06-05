import importlib
import sys
import types
from unittest.mock import MagicMock, Mock

import pytest
from httpx import RequestError, Response

from soar_sdk.apis.utils import get_request_iter_pages
from soar_sdk.app_client import BasicAuth
from soar_sdk.exceptions import SoarAPIError


@pytest.fixture
def platform_vault(monkeypatch):
    import soar_sdk.shims.phantom.vault as vault_shim

    phantom_module = types.ModuleType("phantom")
    phantom_vault_module = types.ModuleType("phantom.vault")

    class FakeVault:
        @staticmethod
        def get_vault_tmp_dir():
            return "/opt/phantom/vault/tmp"

    vault_add = Mock(return_value=(True, "Attachment added", "vault-id"))
    phantom_vault_module.Vault = FakeVault
    phantom_vault_module.vault_add = vault_add
    phantom_vault_module.vault_delete = Mock(return_value=(True, "", []))
    phantom_vault_module.vault_info = Mock(return_value=(True, "", []))
    phantom_module.vault = phantom_vault_module

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "phantom", phantom_module)
        mp.setitem(sys.modules, "phantom.vault", phantom_vault_module)
        reloaded_vault_shim = importlib.reload(vault_shim)
        yield reloaded_vault_shim, vault_add

    importlib.reload(vault_shim)


def test_vault_get_temp_dir(app_connector):
    assert app_connector.vault.get_vault_tmp_dir() == "/opt/phantom/vault/tmp"


def test_platform_vault_add_attachment_returns_vault_id(platform_vault):
    vault_shim, vault_add = platform_vault
    vault = vault_shim.PhantomVault(MagicMock())

    vault_id = vault.add_attachment(
        container_id=1,
        file_location="/opt/phantom/vault/tmp/test.txt",
        file_name="test.txt",
        metadata={"source": "test"},
    )

    assert vault_id == "vault-id"
    vault_add.assert_called_once_with(
        1,
        "/opt/phantom/vault/tmp/test.txt",
        "test.txt",
        {"source": "test"},
    )


def test_platform_vault_add_attachment_failed_tuple(platform_vault):
    vault_shim, vault_add = platform_vault
    vault_add.return_value = (False, "Vault upload failed", None)
    vault = vault_shim.PhantomVault(MagicMock())

    with pytest.raises(SoarAPIError, match="Vault upload failed"):
        vault.add_attachment(
            container_id=1,
            file_location="/opt/phantom/vault/tmp/test.txt",
            file_name="test.txt",
            metadata={},
        )


def test_platform_vault_add_attachment_missing_vault_id(platform_vault):
    vault_shim, vault_add = platform_vault
    vault_add.return_value = (True, "Vault ID missing", None)
    vault = vault_shim.PhantomVault(MagicMock())

    with pytest.raises(SoarAPIError, match="Vault ID missing"):
        vault.add_attachment(
            container_id=1,
            file_location="/opt/phantom/vault/tmp/test.txt",
            file_name="test.txt",
            metadata={},
        )


def test_vault_create_attachment(app_connector, mock_post_vault):
    app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test.txt",
        metadata={},
    )

    assert mock_post_vault.called


def test_vault_create_attachment_exception(app_connector, mock_post_vault):
    mock_post_vault.side_effect = RequestError("Failed to create container")
    with pytest.raises(SoarAPIError):
        app_connector.vault.create_attachment(
            container_id=1,
            file_content="test content",
            file_name="test.txt",
            metadata={},
        )


def test_vault_create_attachment_failed(app_connector, mock_post_vault):
    mock_post_vault.return_value = Response(
        500, json={"failed": "something went wrong"}
    )
    with pytest.raises(SoarAPIError):
        app_connector.vault.create_attachment(
            container_id=1,
            file_content="test content",
            file_name="test.txt",
            metadata={},
        )


def test_vault_create_attachment_unath_client(app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    vault_id = app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test.txt",
        metadata={},
    )
    vault_entry = app_connector.vault.get_attachment(vault_id=vault_id)
    assert vault_entry[0].vault_id == vault_id
    assert vault_entry[0].name == "test.txt"
    assert vault_entry[0].container_id == 1


def test_vault_add_attachment(app_connector, mock_post_vault):
    app_connector.vault.add_attachment(
        container_id=1,
        file_location="/opt/phantom/vault/tmp/test.txt",
        file_name="test.txt",
        metadata={},
    )

    assert mock_post_vault.called


def test_vault_add_attachment_unath_client(app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    vault_id = app_connector.vault.add_attachment(
        container_id=1,
        file_location="/opt/phantom/vault/tmp/test.txt",
        file_name="test.txt",
        metadata={},
    )
    vault_entry = app_connector.vault.get_attachment(vault_id=vault_id)
    assert vault_entry[0].vault_id == vault_id
    assert vault_entry[0].name == "test.txt"
    assert vault_entry[0].container_id == 1
    assert vault_entry[0].path == "/opt/phantom/vault/tmp/test.txt"


def test_vault_add_attachment_exception(app_connector, mock_post_vault):
    mock_post_vault.side_effect = RequestError("Failed to create container")
    with pytest.raises(SoarAPIError):
        app_connector.vault.add_attachment(
            container_id=1,
            file_location="/opt/phantom/vault/tmp/test.txt",
            file_name="test.txt",
            metadata={},
        )


def test_vault_add_attachment_failed(app_connector, mock_post_vault):
    mock_post_vault.return_value = Response(
        500, json={"failed": "something went wrong"}
    )
    with pytest.raises(SoarAPIError):
        app_connector.vault.add_attachment(
            container_id=1,
            file_location="/opt/phantom/vault/tmp/test.txt",
            file_name="test.txt",
            metadata={},
        )


def test_vault_delete_attachment(app_connector):
    app_connector.client.headers.pop("X-CSRFToken")
    vault_id = app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test.txt",
        metadata={},
    )
    assert app_connector.vault.get_attachment(vault_id=vault_id)[0].vault_id == vault_id
    deleted_files = app_connector.vault.delete_attachment(
        vault_id=vault_id,
    )
    assert deleted_files == ["test.txt"]


def test_vault_delete_attachment_authenticated_client(
    app_connector, mock_get_vault, mock_delete_vault
):
    app_connector._AppClient__basic_auth = BasicAuth(
        username="username", password="password"
    )
    deleted_files = app_connector.vault.delete_attachment(
        vault_id="1",
    )

    assert deleted_files == ["test.txt"]
    assert mock_get_vault.called
    assert mock_delete_vault.called
    app_connector._AppClient__basic_auth = None


def test_vault_delete_attachment_authenticated_client_error(
    app_connector, mock_get_vault, mock_delete_vault
):
    mock_delete_vault.side_effect = RequestError("Authentication error")
    with pytest.raises(SoarAPIError):
        app_connector.vault.delete_attachment(
            vault_id="1",
        )

    assert mock_get_vault.called


def test_vault_delete_attachment_authenticated_client_failed(
    app_connector, mock_get_vault, mock_delete_vault
):
    mock_delete_vault.return_value = Response(
        401, json={"failed": "something went wrong", "message": "Authentication error"}
    )
    with pytest.raises(SoarAPIError):
        app_connector.vault.delete_attachment(
            vault_id="1",
        )

    assert mock_get_vault.called


def test_vault_multiple_attachments_to_delete(app_connector):
    app_connector.client.headers.pop("X-CSRFToken")
    app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test.txt",
        metadata={},
    )
    app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test2.txt",
        metadata={},
    )
    items = app_connector.vault.get_attachment(container_id=1)
    assert len(items) == 2
    with pytest.raises(
        SoarAPIError,
        match="More than one document found with the information provided and remove_all is set to False, no vault items were deleted.",
    ):
        app_connector.vault.delete_attachment(
            container_id=1,
        )


def test_get_iter_pages(app_connector, mock_get_vault):
    for res in get_request_iter_pages(
        app_connector.client, "rest/container_attachment", params={"container_id": 1}
    ):
        assert res[0]["container_id"] == 1
        assert res[0]["id"] == 1
        assert res[0]["name"] == "test.txt"

    assert mock_get_vault.called


def test_open_vault_attachment(app_connector, tmp_path):
    app_connector.client.headers.pop("X-CSRFToken")

    tmp_file = tmp_path / "test.txt"
    tmp_file.write_text("test content")

    vault_id = app_connector.vault.create_attachment(
        container_id=1,
        file_content="test content",
        file_name="test.txt",
        metadata={},
    )
    vault_entry = app_connector.vault.get_attachment(vault_id=vault_id)
    vault_entry[0].path = str(tmp_file)  # Simulate the file path
    assert vault_entry[0].open().read() == "test content"
