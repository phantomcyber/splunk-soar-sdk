from typing import IO, Optional, Union
from pydantic import BaseModel


class VaultAttachment(BaseModel):
    """Model representing a vault attachment.

    This model is used to represent the metadata and content of a file stored
    in the SOAR vault. It includes attributes such as vault ID, file name,
    size, metadata, and the file path.
    """

    id: int
    created_via: Optional[str] = None
    container: str
    task: Optional[str] = None
    create_time: str
    name: str
    user: str
    vault_document: int
    mime_type: Optional[str] = None
    es_attachment_id: Optional[str] = None
    hash: str
    vault_id: str
    size: int
    path: str
    metadata: dict = {}
    aka: list[str] = []
    container_id: int
    contains: list[str] = []

    def open(self, mode: str = "r") -> Union[IO[str], IO[bytes]]:
        """Open the vault attachment file.

        Args:
            mode (str): The mode in which to open the file. Defaults to 'r'.

        Returns:
            file: A file-like object for reading the attachment content.
        """
        return open(self.path, mode)
