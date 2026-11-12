__lazy_modules__ = {
    "collections.abc",
    "importlib",
    "pydantic",
    "soar_sdk.exceptions",
    "soar_sdk.models.attachment_upload",
    "typing",
}

from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError

from soar_sdk.exceptions import ActionFailure, AttachmentApiError
from soar_sdk.models.attachment_upload import (
    AttachmentUploadTarget,
    NonBlankStr,
    SubjectAttachmentAssociation,
)

_BRIDGE_MODULE = "attachment_api"

_HIDE_INPUT = ConfigDict(hide_input_in_errors=True)
_FILE_NAMES: TypeAdapter[list[str]] = TypeAdapter(
    Annotated[list[NonBlankStr], Field(min_length=1)], config=_HIDE_INPUT
)
_IDEMPOTENCY_KEY: TypeAdapter[str] = TypeAdapter(NonBlankStr, config=_HIDE_INPUT)
_MESSAGE_ID: TypeAdapter[str] = TypeAdapter(
    Annotated[NonBlankStr, Field(strict=True)], config=_HIDE_INPUT
)
_TARGETS: TypeAdapter[list[AttachmentUploadTarget]] = TypeAdapter(
    list[AttachmentUploadTarget], config=_HIDE_INPUT
)
_ASSOCIATIONS: TypeAdapter[list[SubjectAttachmentAssociation]] = TypeAdapter(
    Annotated[list[SubjectAttachmentAssociation], Field(min_length=1)],
    config=_HIDE_INPUT,
)


@runtime_checkable
class AttachmentBridge(Protocol):
    """The attachment bridge contract supplied by the ingestion runtime bundle."""

    def get_upload_targets(
        self, file_names: list[str], idempotency_key: str
    ) -> list[dict[str, Any]]:
        """Reserve attachment identities and return presigned targets."""
        ...

    def associate_subject_attachments(
        self, associations: list[SubjectAttachmentAssociation]
    ) -> str:
        """Queue subject associations and return the message ID."""
        ...


def _load_bridge() -> AttachmentBridge:
    """Load the execution bundle's bridge only when an attachment API is used."""
    try:
        bridge = import_module(_BRIDGE_MODULE)
    except Exception as error:
        if isinstance(error, ModuleNotFoundError) and error.name == _BRIDGE_MODULE:
            message = "Attachment APIs require an ingestion runtime bundle."
        else:
            message = "The attachment runtime bridge failed to load."
    else:
        if not isinstance(bridge, AttachmentBridge):
            raise AttachmentApiError("The attachment runtime bridge is invalid.")
        return bridge
    raise AttachmentApiError(message) from None


def _invoke_bridge[ResultT](operation: Callable[[], ResultT], message: str) -> ResultT:
    """Report a runtime failure after its exception context has been cleared."""
    try:
        return operation()
    except Exception:
        error = AttachmentApiError(message)
    raise error from None


def _validate_payload[PayloadT](
    adapter: TypeAdapter[PayloadT],
    payload: object,
    error_type: type[ActionFailure],
    message: str,
) -> PayloadT:
    """Validate without retaining the original error or raw payload on failure."""
    try:
        return adapter.validate_python(payload)
    except ValidationError:
        pass
    # Error reporters may capture locals from the SDK traceback frames.
    del payload
    raise error_type(message) from None


class Attachments:
    """API interface for attachment records and finding associations.

    Operations delegate to the attachment bridge supplied by an
    ingestion runtime bundle. The bridge enforces ``on_es_poll`` execution and
    supplies the accepted task's tenant and credentials. Failures raised by the
    bridge are reported as :class:`~soar_sdk.exceptions.AttachmentApiError`.
    Runtime failures use fixed SDK messages. The upstream exception is not
    retained as ``__cause__`` or ``__context__``, keeping its credentials out of
    SDK errors and tracebacks.
    """

    def __init__(self, bridge: AttachmentBridge | None = None) -> None:
        """Initialize the attachment API.

        Args:
            bridge: The runtime bridge to call. When omitted, the bridge is
                loaded from the execution bundle on first use and reused.
        """
        self._bridge = bridge

    def _get_bridge(self) -> AttachmentBridge:
        if self._bridge is None:
            self._bridge = _load_bridge()
        return self._bridge

    def get_upload_targets(
        self, file_names: Sequence[str], idempotency_key: str
    ) -> list[AttachmentUploadTarget]:
        """Reserve attachment identities and request presigned upload targets.

        No bytes are uploaded here.

        Args:
            file_names: Names of the files in this batch, in order. The runtime
                service accepts 1 through 20 names per batch.
            idempotency_key: UUID identifying this batch. Reuse it with the same
                file names when retrying target creation.

        Returns:
            One target per requested file name, in request order.

        Raises:
            ActionFailure: If ``file_names`` or ``idempotency_key`` is invalid.
            AttachmentApiError: If the runtime bridge is unavailable, fails, or
                returns invalid targets, mismatched file names, or duplicate
                attachment IDs.
        """
        invalid_request = (
            "Attachment upload targets require nonempty file names and "
            "an idempotency key."
        )
        names = _validate_payload(
            _FILE_NAMES, file_names, ActionFailure, invalid_request
        )
        key = _validate_payload(
            _IDEMPOTENCY_KEY, idempotency_key, ActionFailure, invalid_request
        )
        bridge = self._get_bridge()
        # Keep the raw signed targets out of this frame's locals on error.
        validated = _validate_payload(
            _TARGETS,
            _invoke_bridge(
                lambda: bridge.get_upload_targets(names, key),
                "Attachment record creation failed.",
            ),
            AttachmentApiError,
            "Invalid attachment upload targets returned by runtime.",
        )
        if [target.file_name for target in validated] != names:
            raise AttachmentApiError(
                "Attachment upload targets do not match requested files."
            )
        if len({target.attachment_id for target in validated}) != len(validated):
            raise AttachmentApiError(
                "Attachment upload targets contain duplicate attachment IDs."
            )
        return validated

    def associate_subject_attachments(
        self, associations: Sequence[SubjectAttachmentAssociation]
    ) -> str:
        """Queue attachment associations after ES creates the findings.

        Args:
            associations: Mappings with ``subject_id`` (the ES finding ID) and
                ``attachment_ids`` (the stable IDs returned by
                :meth:`get_upload_targets`).

        Returns:
            The durable queue message ID. This acknowledges enqueueing, not
            completion of the association in Timeline.

        Raises:
            ActionFailure: If ``associations`` is empty or invalid.
            AttachmentApiError: If the runtime bridge is unavailable, fails, or
                returns an invalid message ID.
        """
        validated = _validate_payload(
            _ASSOCIATIONS,
            associations,
            ActionFailure,
            "At least one valid subject attachment association is required.",
        )
        bridge = self._get_bridge()
        return _validate_payload(
            _MESSAGE_ID,
            _invoke_bridge(
                lambda: bridge.associate_subject_attachments(validated),
                "Attachment association failed.",
            ),
            AttachmentApiError,
            "Runtime returned an invalid attachment association message ID.",
        )
