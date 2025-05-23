from httpx import Response, RequestError
from soar_sdk.exceptions import SoarAPIError
from soar_sdk.connector import BasicAuth
import pytest
from soar_sdk.apis.utils import get_request_iter_pages


def test_vault_get_temp_dir(app_connector):
    assert app_connector.vault.get_vault_tmp_dir() == "/opt/phantom/vault/tmp"


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
    assert vault_entry[0]["id"] == vault_id
    assert vault_entry[0]["name"] == "test.txt"
    assert vault_entry[0]["container_id"] == 1


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
    assert vault_entry[0]["id"] == vault_id
    assert vault_entry[0]["name"] == "test.txt"
    assert vault_entry[0]["container_id"] == 1
    assert vault_entry[0]["file_path"] == "/opt/phantom/vault/tmp/test.txt"


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
    assert app_connector.vault.get_attachment(vault_id=vault_id)[0]["id"] == vault_id
    deleted_files = app_connector.vault.delete_attachment(
        vault_id=vault_id,
    )
    assert deleted_files == ["test.txt"]


def test_vault_delete_attachment_authenticated_client(
    app_connector, mock_get_vault, mock_delete_vault
):
    app_connector._AppConnector__basic_auth = BasicAuth(
        username="username", password="password"
    )
    deleted_files = app_connector.vault.delete_attachment(
        vault_id="1",
    )

    assert deleted_files == ["test.txt"]
    assert mock_get_vault.called
    assert mock_delete_vault.called
    app_connector._AppConnector__basic_auth = None


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
