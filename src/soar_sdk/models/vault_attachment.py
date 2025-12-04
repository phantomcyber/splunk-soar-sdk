from typing import IO

from pydantic import BaseModel


class VaultAttachment(BaseModel):
    """Model representing a vault attachment.

    This model is used to represent the metadata and content of a file stored
    in the SOAR vault. It includes attributes such as vault ID, file name,
    size, metadata, and the file path.
    """

    id: int
    created_via: str | None = None
    container: str
    task: str | None = None
    create_time: str
    name: str
    user: str
    vault_document: int
    mime_type: str | None = None
    es_attachment_id: str | None = None
    hash: str
    vault_id: str
    size: int
    path: str
    metadata: dict = {}
    aka: list[str] = []
    container_id: int
    contains: list[str] = []

    def open(self, mode: str = "r") -> IO[str] | IO[bytes]:
        """Open the vault attachment file.

        Args:
            mode (str): The mode in which to open the file. Defaults to 'r'.

        Returns:
            file: A file-like object for reading the attachment content.
        """
        return open(self.path, mode)
