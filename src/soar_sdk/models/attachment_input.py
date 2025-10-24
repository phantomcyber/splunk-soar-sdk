from typing import Optional, Union
from pydantic import BaseModel, field_validator, ConfigDict


class AttachmentInput(BaseModel):
    """Represents a vault attachment to be created during on_es_poll.

    Specify either file_content OR file_location, not both.
    """

    model_config = ConfigDict(extra="forbid")

    file_content: Optional[Union[str, bytes]] = None
    file_location: Optional[str] = None
    file_name: str
    metadata: Optional[dict[str, str]] = None

    @field_validator("file_location")
    @classmethod
    def validate_one_source(cls, v: Optional[str], info) -> Optional[str]:
        file_content = info.data.get("file_content")
        if v is None and file_content is None:
            raise ValueError("Must provide either file_content or file_location")
        if v is not None and file_content is not None:
            raise ValueError("Cannot provide both file_content and file_location")
        return v
