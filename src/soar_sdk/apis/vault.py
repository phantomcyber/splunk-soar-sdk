try:
    from phantom.rules import vault_add, vault_delete, vault_info
    from phantom.vault import Vault as PhantomVault

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING, Optional, Union, Any
from pathlib import Path
import tempfile
import json
from soar_sdk.exceptions import SoarAPIError
from dataclasses import dataclass, asdict
from soar_sdk.apis.utils import is_client_authenticated, get_request_iter_pages
from soar_sdk.logging import getLogger

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient


VAULT_ENDPOINT = "rest/container_attachment"
logger = getLogger()


@dataclass
class VaultEntry:
    id: int
    file_path: str
    name: str
    container_id: int


class Vault:
    def __init__(self, soar_client: "SOARClient"):
        self.soar_client: SOARClient = soar_client
        self.__storage = {}

    def get_vault_tmp_dir(self) -> str:
        """
        Returns the vault tmp directory.
        """
        if _soar_is_available:
            return PhantomVault.get_vault_tmp_dir()
        else:
            return "/opt/phantom/vault/tmp"

    def get_next_vault_id(self) -> int:
        return max(self.__storage.keys()) if self.__storage else 0 + 1

    def create_attachment(
        self,
        container_id: int,
        file_content: Any,
        file_name: str,
        metadata: dict[str, str] = None,
    ) -> int:
        """
        Creates a vault attachment from file content.
        """
        if _soar_is_available:
            _, _, vault_id = PhantomVault.create_attachment(
                file_content, container_id, file_name, metadata
            )
        else:
            if is_client_authenticated(self.soar_client.client):
                data = {
                    "container_id": container_id,
                    "file_content": file_content,
                    "file_name": file_name,
                    "metadata": metadata,
                }
                headers = {
                    "Referer": f"{self.soar_client.client.base_url}/{VAULT_ENDPOINT}"
                }
                try:
                    response = self.soar_client.client.post(
                        VAULT_ENDPOINT, headers=headers, data=json.dumps(data)
                    )
                    resp_json = response.json()
                except Exception as e:
                    error_msg = f"Failed to add attachment to the Vault: {e}"
                    raise SoarAPIError(error_msg) from e

                if resp_json.get("failed"):
                    reason = resp_json.get("message", "NONE_GIVEN")
                    error_msg = f"Failed to add attachment to the Vault: {reason}"
                    raise SoarAPIError(error_msg) from e

                vault_id = resp_json.get("vault_id")
            else:
                with tempfile.TemporaryDirectory() as temp_dir:
                    file_path = Path(temp_dir) / file_name
                    file_path.write_text(file_content)

                vault_id = self.get_next_vault_id()
                self.__storage[vault_id] = VaultEntry(
                    id=vault_id,
                    file_path=temp_dir,
                    name=file_name,
                    container_id=container_id,
                )

        return vault_id

    def add_attachment(
        self,
        container_id: int,
        file_location: str,
        file_name: str,
        metadata: dict[str, str] = None,
    ) -> int:
        """
        Add an attachment to vault.
        """
        if _soar_is_available:
            self.soar_client.debug(f"Adding file to vault: {file_location}")
            self.soar_client.debug(f"Adding file to vault: {file_location}")
            success, message, vault_id = vault_add(
                container_id, file_location, file_name, metadata
            )
            if not success:
                raise SoarAPIError(message)

        else:
            metadata = metadata or {}

            if is_client_authenticated(self.soar_client.client):
                if not str(file_location).startswith(self.get_vault_tmp_dir()):
                    # We fail automatically when running through the cli if the file is not in the vault tmp directory
                    raise ValueError(
                        f"File location must be in {self.get_vault_tmp_dir()} directory: {file_location}"
                    )

                data = {
                    "container_id": container_id,
                    "local_path": file_location,
                    "file_name": file_name,
                    "metadata": metadata,
                }

                headers = {
                    "Referer": f"{self.soar_client.client.base_url}/{VAULT_ENDPOINT}"
                }
                try:
                    response = self.soar_client.client.post(
                        VAULT_ENDPOINT, headers=headers, data=json.dumps(data)
                    )
                    resp_json = response.json()
                except Exception as e:
                    error_msg = f"Failed to add attachment to the Vault: {e}"
                    raise SoarAPIError(error_msg) from e

                if resp_json.get("failed"):
                    reason = resp_json.get("message", "NONE_GIVEN")
                    error_msg = f"Failed to add attachment to the Vault: {reason}"
                    raise SoarAPIError(error_msg)
                vault_id = resp_json.get("vault_id")
            else:
                vault_id = self.get_next_vault_id()
                self.__storage[vault_id] = VaultEntry(
                    id=vault_id,
                    file_path=file_location,
                    name=file_name,
                    container_id=container_id,
                )

        return vault_id

    def get_attachment(
        self,
        vault_id: Optional[int] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        download_file: bool = True,
    ) -> dict[str, Any]:
        """
        Get an attachment from vault.
        """
        if not any([vault_id, file_name, container_id]):
            raise ValueError(
                "Must provide either vault_id, file_name or container_id when getting a file from the Vault."
            )

        if _soar_is_available:
            return vault_info(vault_id, file_name, download_file=download_file)
        else:
            results = []
            if is_client_authenticated(self.soar_client.client):
                query_params: dict[str, Union[str, int]] = {"pretty": ""}
                if vault_id:
                    query_params["_filter_vault_document__hash"] = (
                        f'"{vault_id.lower()}"'
                    )
                if file_name:
                    query_params["_filter_name"] = f'"{file_name}"'
                if container_id:
                    query_params["_filter_container_id"] = container_id

                for page_data in get_request_iter_pages(
                    self.soar_client.client, VAULT_ENDPOINT, params=query_params
                ):
                    for res in page_data:
                        keys_to_filter = [
                            key for key in res if key.startswith("_pretty_")
                        ]
                        for key in keys_to_filter:
                            res[key[8:]] = res.pop(key)
                        results.append(res)
            else:
                if vault_id:
                    res = self.__storage.get(vault_id)
                    if res:
                        results.append(asdict(res))

                if any(vault_id, file_name):
                    for id, res in self.__storage.items():
                        if file_name in res.file_path or container_id in res.file_path:
                            results.append(asdict(res))

            return results

    def delete_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        remove_all: bool = False,
    ) -> list[str]:
        if _soar_is_available:
            _, _, deleted_file_names = vault_delete(
                vault_id, file_name, container_id, remove_all
            )
        else:
            vault_enteries = self.get_attachment(vault_id, file_name, container_id)
            deleted_file_names = []
            is_authenticated = is_client_authenticated(self.soar_client.client)
            for attachment in vault_enteries:
                attachment_id = attachment.get("id")
                attachment_name = attachment.get("name")
                if is_authenticated:
                    logger.warning(
                        "SOAR client is authenticated, but deleting files via the cli is only supported via basic auth. As a result, the attachment will not be deleted."
                    )
                else:
                    self.__storage.pop(attachment_id)

                deleted_file_names.append(attachment_name)

        return deleted_file_names
