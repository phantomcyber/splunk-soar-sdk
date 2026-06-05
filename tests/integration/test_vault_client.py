from contextlib import suppress
from uuid import uuid4

from soar_sdk.models.vault_attachment import VaultAttachment

from .soar_client import AppOnStackClient


def _get_matching_attachment(
    client: AppOnStackClient, vault_id: str, file_name: str
) -> VaultAttachment:
    attachments = client.phantom.vault.get_attachment(vault_id=vault_id)
    matching_attachments = [
        attachment for attachment in attachments if attachment.vault_id == vault_id
    ]

    assert len(matching_attachments) == 1
    attachment = matching_attachments[0]
    assert attachment.name == file_name
    return attachment


def _delete_vault_id(client: AppOnStackClient, vault_id: str) -> list[str]:
    return client.phantom.vault.delete_attachment(vault_id=vault_id)


def test_vault_create_get_delete_attachment(example_app_client: AppOnStackClient):
    container_id = example_app_client.container_id
    assert container_id is not None

    test_id = uuid4().hex
    file_name = f"sdk-vault-create-{test_id}.txt"
    file_content = f"vault create integration test content {test_id}"
    metadata = {"sdk_integration_test": test_id, "operation": "create"}
    vault_id: str | None = None

    try:
        vault_id = example_app_client.phantom.vault.create_attachment(
            container_id=container_id,
            file_content=file_content,
            file_name=file_name,
            metadata=metadata,
        )

        assert vault_id

        attachment = _get_matching_attachment(example_app_client, vault_id, file_name)
        assert attachment.container_id == container_id
        assert attachment.metadata.get("sdk_integration_test") == test_id
        assert attachment.metadata.get("operation") == "create"

        attachments_by_name = example_app_client.phantom.vault.get_attachment(
            file_name=file_name
        )
        assert any(
            attachment.vault_id == vault_id for attachment in attachments_by_name
        )

        attachments_by_container = example_app_client.phantom.vault.get_attachment(
            container_id=container_id
        )
        assert any(
            attachment.vault_id == vault_id for attachment in attachments_by_container
        )

        deleted_vault_id = vault_id
        deleted_file_names = _delete_vault_id(example_app_client, deleted_vault_id)
        assert file_name in deleted_file_names
        vault_id = None

        assert (
            example_app_client.phantom.vault.get_attachment(vault_id=deleted_vault_id)
            == []
        )
    finally:
        if vault_id is not None:
            with suppress(Exception):
                _delete_vault_id(example_app_client, vault_id)


def test_vault_add_get_delete_attachment(example_app_client: AppOnStackClient):
    container_id = example_app_client.container_id
    assert container_id is not None

    test_id = uuid4().hex
    file_name = f"sdk-vault-add-{test_id}.txt"
    file_content = f"vault add integration test content {test_id}"
    metadata = {"sdk_integration_test": test_id, "operation": "add"}
    vault_id: str | None = None

    stage_result = example_app_client.run_action(
        "stage vault tmp file",
        {"file_name": file_name, "file_content": file_content},
    )
    assert stage_result.success, f"Stage vault tmp file failed: {stage_result.message}"

    staged_file_path = stage_result.data["data"][0]["file_path"]
    assert staged_file_path.endswith(file_name)

    try:
        vault_id = example_app_client.phantom.vault.add_attachment(
            container_id=container_id,
            file_location=staged_file_path,
            file_name=file_name,
            metadata=metadata,
        )

        assert vault_id

        attachment = _get_matching_attachment(example_app_client, vault_id, file_name)
        assert attachment.container_id == container_id
        assert attachment.metadata.get("sdk_integration_test") == test_id
        assert attachment.metadata.get("operation") == "add"
        assert attachment.path

        deleted_vault_id = vault_id
        deleted_file_names = _delete_vault_id(example_app_client, deleted_vault_id)
        assert file_name in deleted_file_names
        vault_id = None

        assert (
            example_app_client.phantom.vault.get_attachment(vault_id=deleted_vault_id)
            == []
        )
    finally:
        if vault_id is not None:
            with suppress(Exception):
                _delete_vault_id(example_app_client, vault_id)
