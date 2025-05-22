from typing import TYPE_CHECKING, Optional, Any, Union
from soar_sdk.shims.phantom.vault import PhantomVault, VaultBase

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient


class Vault:
    def __init__(self, soar_client: "SOARClient") -> None:
        self.phantom_vault: VaultBase = PhantomVault(soar_client)

    def get_vault_tmp_dir(self) -> str:
        """
        Returns the vault tmp directory.
        """
        return self.phantom_vault.get_vault_tmp_dir()

    def create_attachment(
        self,
        container_id: int,
        file_content: Union[str, bytes],
        file_name: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Creates a vault attachment from file content.
        """
        return self.phantom_vault.create_attachment(
            container_id, file_content, file_name, metadata
        )

    def add_attachment(
        self,
        container_id: int,
        file_location: str,
        file_name: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Add an attachment to vault.
        """
        return self.phantom_vault.add_attachment(
            container_id, file_location, file_name, metadata
        )

    def get_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        download_file: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get an attachment from vault.
        """
        return self.phantom_vault.get_attachment(
            vault_id, file_name, container_id, download_file
        )

    def delete_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        remove_all: bool = False,
    ) -> list[str]:
        return self.phantom_vault.delete_attachment(
            vault_id, file_name, container_id, remove_all
        )
