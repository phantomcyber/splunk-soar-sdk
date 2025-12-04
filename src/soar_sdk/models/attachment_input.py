from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core.core_schema import ValidationInfo


class AttachmentInput(BaseModel):
    """Represents a vault attachment to be created during on_es_poll.

    Specify either file_content OR file_location, not both.
    """

    model_config = ConfigDict(extra="forbid")

    file_content: str | bytes | None = None
    file_location: str | None = None
    file_name: str
    metadata: dict[str, str] | None = None

    @field_validator("file_location")
    @classmethod
    def validate_one_source(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validate that exactly one of file_content or file_location is provided."""
        file_content = info.data.get("file_content")
        if v is None and file_content is None:
            raise ValueError("Must provide either file_content or file_location")
        if v is not None and file_content is not None:
            raise ValueError("Cannot provide both file_content and file_location")
        return v
