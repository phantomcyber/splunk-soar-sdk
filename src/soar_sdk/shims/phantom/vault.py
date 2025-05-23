from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient
from abc import abstractmethod
from soar_sdk.exceptions import SoarAPIError


class VaultBase:
    def __init__(self, soar_client: "SOARClient") -> None:
        self.soar_client: SOARClient = soar_client

    @abstractmethod
    def get_vault_tmp_dir(self) -> str:
        """
        Returns the vault tmp directory.
        """
        pass

    @abstractmethod
    def create_attachment(
        self,
        container_id: int,
        file_content: Union[str, bytes],
        file_name: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Creates a vault attachment from file content. This differs from add_attachment because it doesn't require the file to exist locally.
        """
        pass

    @abstractmethod
    def add_attachment(
        self,
        container_id: int,
        file_location: str,
        file_name: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Add an attachment to vault. This requires the file to exist locally.
        """
        pass

    @abstractmethod
    def get_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        download_file: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Returns vault attachments based on the provided query parameters
        """
        pass

    @abstractmethod
    def delete_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        remove_all: bool = False,
    ) -> list[str]:
        """
        Deletes vault attachments based on the provided query parameters
        """
        pass


PhantomVault: type[VaultBase]

try:
    from phantom.rules import vault_add, vault_delete, vault_info
    from phantom.vault import Vault

    _soar_is_available = True
except ImportError:
    _soar_is_available = False


if _soar_is_available:

    class PhantomVaultPlatform(VaultBase):
        def get_vault_tmp_dir(self) -> str:
            return Vault.get_vault_tmp_dir()

        def create_attachment(
            self,
            container_id: int,
            file_content: Union[str, bytes],
            file_name: str,
            metadata: Optional[dict[str, str]] = None,
        ) -> str:
            resp_json = Vault.create_attachment(
                file_content, container_id, file_name, metadata
            )
            if not resp_json.get("succeeded"):
                error_msg = resp_json.get("message", "Could not create attachment")
                raise SoarAPIError(error_msg)
            return resp_json["vault_id"]

        def add_attachment(
            self,
            container_id: int,
            file_location: str,
            file_name: str,
            metadata: Optional[dict[str, str]] = None,
        ) -> str:
            resp_json = vault_add(container_id, file_location, file_name, metadata)
            if not resp_json.get("succeeded"):
                error_msg = resp_json.get("message", "Could not add attachment")
                raise SoarAPIError(error_msg)
            return resp_json["vault_id"]

        def get_attachment(
            self,
            vault_id: Optional[str] = None,
            file_name: Optional[str] = None,
            container_id: Optional[int] = None,
            download_file: bool = True,
        ) -> list[dict[str, Any]]:
            return vault_info(
                vault_id, file_name, container_id, download_file=download_file
            )

        def delete_attachment(
            self,
            vault_id: Optional[str] = None,
            file_name: Optional[str] = None,
            container_id: Optional[int] = None,
            remove_all: bool = False,
        ) -> list[str]:
            success, message, deleted_file_names = vault_delete(
                vault_id=vault_id,
                file_name=file_name,
                container_id=container_id,
                remove_all=remove_all,
            )
            if not success:
                raise SoarAPIError(message)
            return deleted_file_names

    PhantomVault = PhantomVaultPlatform

else:
    from soar_sdk.apis.utils import is_client_authenticated, get_request_iter_pages
    import tempfile
    from pathlib import Path
    import secrets
    from dataclasses import dataclass, asdict
    from soar_sdk.logging import getLogger

    VAULT_ENDPOINT = "rest/container_attachment"
    logger = getLogger()

    @dataclass
    class VaultEntry:
        id: int
        file_path: str
        name: str
        container_id: int

    class PhantomVaultFallback(VaultBase):
        def __init__(self, soar_client: "SOARClient") -> None:
            super().__init__(soar_client)
            self.__storage: dict[str, VaultEntry] = {}

        def get_vault_tmp_dir(self) -> str:
            return "/opt/phantom/vault/tmp"

        def create_attachment(
            self,
            container_id: int,
            file_content: Union[str, bytes],
            file_name: str,
            metadata: Optional[dict[str, str]] = None,
        ) -> str:
            if is_client_authenticated(self.soar_client.client):
                data = {
                    "container_id": container_id,
                    "file_content": file_content,
                    "file_name": file_name,
                    "metadata": metadata or {},
                }

                try:
                    response = self.soar_client.post(VAULT_ENDPOINT, json=data)
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
                with tempfile.TemporaryDirectory() as temp_dir:
                    file_path = Path(temp_dir) / file_name
                    if isinstance(file_content, bytes):
                        file_content = file_content.decode("utf-8")
                    file_path.write_text(file_content)

                vault_id = secrets.token_hex(20)
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
            metadata: Optional[dict[str, str]] = None,
        ) -> str:
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

                try:
                    response = self.soar_client.post(VAULT_ENDPOINT, json=data)
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
                vault_id = secrets.token_hex(20)
                self.__storage[vault_id] = VaultEntry(
                    id=vault_id,
                    file_path=file_location,
                    name=file_name,
                    container_id=container_id,
                )

            return vault_id

        def get_attachment(
            self,
            vault_id: Optional[str] = None,
            file_name: Optional[str] = None,
            container_id: Optional[int] = None,
            download_file: bool = True,
        ) -> list[dict[str, Any]]:
            if not any([vault_id, file_name, container_id]):
                raise ValueError(
                    "Must provide either vault_id, file_name or container_id when getting a file from the Vault."
                )

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

                if any((container_id, file_name)):
                    for _, res in self.__storage.items():
                        if (
                            file_name and file_name in res.file_path
                        ) or container_id == res.container_id:
                            results.append(asdict(res))

            return results

        def delete_attachment(
            self,
            vault_id: Optional[str] = None,
            file_name: Optional[str] = None,
            container_id: Optional[int] = None,
            remove_all: bool = False,
        ) -> list[str]:
            vault_enteries = self.get_attachment(vault_id, file_name, container_id)
            if len(vault_enteries) > 1 and not remove_all:
                raise SoarAPIError(
                    "More than one document found with the information provided and remove_all is set to False, no vault items were deleted."
                )
            deleted_file_names = []
            is_authenticated = is_client_authenticated(self.soar_client.client)
            for attachment in vault_enteries:
                attachment_id = attachment["id"]
                attachment_name = attachment["name"]
                if is_authenticated:
                    endpoint = f"{VAULT_ENDPOINT}/{attachment_id}"
                    try:
                        response = self.soar_client.delete(endpoint)
                    except Exception as e:
                        error_msg = f"Failed to delete attachment from the Vault: {e}"
                        raise SoarAPIError(error_msg) from e

                    if response.status_code != 200:
                        error_msg = f"Failed to delete attachment from the Vault: {response.text}"
                        raise SoarAPIError(error_msg)
                else:
                    self.__storage.pop(attachment_id)

                deleted_file_names.append(attachment_name)

            return deleted_file_names

    PhantomVault = PhantomVaultFallback


__all__ = ["PhantomVault"]
