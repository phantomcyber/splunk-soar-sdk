__lazy_modules__ = {
    "pydantic",
    "typing",
}

from typing import Annotated, TypedDict

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    with_config,
)


class AttachmentUploadFormField(BaseModel):
    """One multipart field supplied by the attachment upload service.

    The value may be a credential. Read it with ``value.get_secret_value()``.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    name: str
    value: SecretStr = Field(repr=False)


class AttachmentUploadTarget(BaseModel):
    """A stable attachment identity and its short-lived multipart upload target.

    Upload URLs and form field values are credentials. They are stored as
    :class:`~pydantic.SecretStr`, so ``repr``, ``model_dump`` and
    ``model_dump_json`` mask them. Read them with ``get_secret_value()`` only
    when uploading, and do not log or store them in findings. Form fields
    retain their order and may contain duplicate names.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    attachment_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    upload_url: SecretStr = Field(min_length=1, repr=False)
    form_fields: list[AttachmentUploadFormField] = Field(repr=False)
    expires_at: AwareDatetime
    max_size_bytes: int = Field(gt=0)


NonBlankStr = Annotated[str, Field(min_length=1, pattern=r"\S")]
"""A string containing at least one non-whitespace character."""


@with_config(ConfigDict(extra="forbid"))
class SubjectAttachmentAssociation(TypedDict):
    """A subject's attachment IDs, queued through the ingestion runtime bridge.

    ``subject_id`` is the opaque ES finding ID. ``attachment_ids`` are the
    stable IDs from :meth:`~soar_sdk.apis.attachments.Attachments.get_upload_targets`.
    Both must be nonblank, and the list must not be empty.
    """

    subject_id: NonBlankStr
    attachment_ids: Annotated[list[NonBlankStr], Field(min_length=1)]
