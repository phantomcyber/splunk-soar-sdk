from typing import TYPE_CHECKING, Optional, Union
from soar_sdk.models.vault_attachment import VaultAttachment
from soar_sdk.shims.phantom.vault import PhantomVault, VaultBase

if TYPE_CHECKING:
    from soar_sdk.abstract import SOARClient


class Vault:
    """API interface for managing SOAR vault operations.

    This class provides methods to interact with the SOAR vault system for
    file storage and retrieval. The vault is used to store files, attachments,
    and other binary data associated with containers and investigations.

    Attributes:
        phantom_vault (VaultBase): The underlying vault implementation for
                                  file operations.
    """

    def __init__(self, soar_client: "SOARClient") -> None:
        """Initialize the Vault API interface.

        Sets up the vault interface using the appropriate vault implementation
        based on the SOAR client configuration.

        Args:
            soar_client (SOARClient): The SOAR client instance for API communication.
        """
        self.phantom_vault: VaultBase = PhantomVault(soar_client)

    def get_vault_tmp_dir(self) -> str:
        """Get the vault temporary directory path.

        Returns the file system path to the temporary directory used by the vault
        for storing temporary files during processing operations.

        Returns:
            str: The absolute path to the vault temporary directory.

        Example:
            >>> vault_tmp = vault_api.get_vault_tmp_dir()
            >>> print(f"Vault temp directory: {vault_tmp}")
        """
        return self.phantom_vault.get_vault_tmp_dir()

    def create_attachment(
        self,
        container_id: int,
        file_content: Union[str, bytes],
        file_name: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """Create a vault attachment from file content.

        Creates a new file in the vault using the provided content and associates
        it with the specified container. The content can be either string or binary data.

        Args:
            container_id (int): The ID of the container to associate the attachment with.
            file_content (Union[str, bytes]): The content of the file to create.
                                             Can be text (str) or binary data (bytes).
            file_name (str): The name to give the file in the vault.
            metadata (Optional[dict[str, str]], optional): Additional metadata
                                                          to associate with the file.
                                                          Defaults to None.

        Returns:
            str: The vault ID of the created attachment.

        Example:
            >>> content = "This is a sample text file content"
            >>> vault_id = vault_api.create_attachment(
            ...     container_id=123,
            ...     file_content=content,
            ...     file_name="sample.txt",
            ...     metadata={"source": "user_upload"},
            ... )
            >>> print(f"Created attachment with vault ID: {vault_id}")
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
        """Add an existing file to the vault as an attachment.

        Takes an existing file from the file system and adds it to the vault,
        associating it with the specified container. The original file is typically
        copied or moved to the vault storage.

        Args:
            container_id (int): The ID of the container to associate the attachment with.
            file_location (str): The file system path to the existing file to add.
            file_name (str): The name to give the file in the vault.
            metadata (Optional[dict[str, str]], optional): Additional metadata
                                                          to associate with the file.
                                                          Defaults to None.

        Returns:
            str: The vault ID of the added attachment.

        Example:
            >>> vault_id = vault_api.add_attachment(
            ...     container_id=123,
            ...     file_location="/tmp/evidence.pdf",
            ...     file_name="evidence_report.pdf",
            ...     metadata={"type": "report", "classification": "internal"},
            ... )
            >>> print(f"Added attachment with vault ID: {vault_id}")
        """
        return self.phantom_vault.add_attachment(
            container_id, file_location, file_name, metadata
        )

    def get_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
    ) -> list[VaultAttachment]:
        """Retrieve attachment(s) from the vault.

        Retrieves one or more attachments from the vault based on the provided
        search criteria. Can search by vault ID, file name, or container ID.

        Args:
            vault_id (Optional[str], optional): The specific vault ID to retrieve.
                                              If provided, returns only that attachment.
                                              Defaults to None.
            file_name (Optional[str], optional): Search for attachments with this
                                               file name. Defaults to None.
            container_id (Optional[int], optional): Search for attachments associated
                                                   with this container. Defaults to None.

        Returns:
            list[VaultAttachment]: List of attachment objects containing
                                metadata and file content. Each object
                                typically includes keys like 'vault_id', 'name',
                                'size', 'metadata', and 'path'.

        Example:
            >>> # Get a specific attachment by vault ID
            >>> attachments = vault_api.get_attachment(vault_id="abc123")
            >>>
            >>> # Get all attachments for a container
            >>> attachments = vault_api.get_attachment(container_id=123)
        """
        return [
            VaultAttachment(**item)
            for item in self.phantom_vault.get_attachment(
                vault_id, file_name, container_id, True
            )
        ]

    def delete_attachment(
        self,
        vault_id: Optional[str] = None,
        file_name: Optional[str] = None,
        container_id: Optional[int] = None,
        remove_all: bool = False,
    ) -> list[str]:
        """Delete attachment(s) from the vault.

        Removes one or more attachments from the vault based on the provided
        search criteria. Can delete by vault ID, file name, or all attachments
        in a container.

        Args:
            vault_id (Optional[str], optional): The specific vault ID to delete.
                                              If provided, deletes only that attachment.
                                              Defaults to None.
            file_name (Optional[str], optional): Delete attachments with this
                                               file name. Defaults to None.
            container_id (Optional[int], optional): Delete attachments associated
                                                   with this container. Defaults to None.
            remove_all (bool, optional): If True and container_id is provided,
                                        removes all attachments from the container.
                                        Defaults to False.

        Returns:
            list[str]: List of vault IDs of the deleted attachments.

        Example:
            >>> # Delete a specific attachment
            >>> deleted = vault_api.delete_attachment(vault_id="abc123")
            >>> print(f"Deleted attachments: {deleted}")
            >>>
            >>> # Delete all attachments from a container
            >>> deleted = vault_api.delete_attachment(container_id=123, remove_all=True)
            >>>
            >>> # Delete attachments by filename
            >>> deleted = vault_api.delete_attachment(file_name="temp_file.txt")
        """
        return self.phantom_vault.delete_attachment(
            vault_id, file_name, container_id, remove_all
        )
