__lazy_modules__ = {
    "collections.abc",
    "contextlib",
    "importlib",
    "pydantic",
    "pathlib",
    "soar_sdk.apis._attachment_upload",
    "soar_sdk.concurrency",
    "soar_sdk.exceptions",
    "soar_sdk.models.attachment_upload",
    "typing",
}

from collections.abc import Callable, Sequence
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError

from soar_sdk.apis._attachment_upload import upload_file
from soar_sdk.concurrency import parallel_map
from soar_sdk.exceptions import ActionFailure, AttachmentApiError, AttachmentUploadError
from soar_sdk.models.attachment_upload import (
    AttachmentUploadOutcome,
    AttachmentUploadResult,
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

    Record reservation and finding association delegate to the attachment bridge
    supplied by an ingestion runtime bundle. File uploads consume its
    presigned targets directly. The bridge enforces ``on_es_poll`` execution and
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

    def upload_file(
        self,
        file_path: str | Path,
        target: AttachmentUploadTarget,
        *,
        timeout: float = 30.0,
    ) -> AttachmentUploadResult:
        """Stream a downloaded file to its presigned multipart POST target.

        Args:
            file_path: Path to the downloaded file. The caller owns cleanup.
            target: Corresponding target returned by ``get_upload_targets``.
                Its ordered form fields, file name and attachment ID are preserved.
            timeout: Positive, finite socket timeout in seconds (default 30).

        Returns:
            A receipt with the existing attachment ID, target name and byte count.

        Raises:
            AttachmentUploadError: On invalid inputs, expired targets, file errors,
                rejected uploads, service failures or timeouts. Errors contain no
                signed URL, form values or response body. There are no retries or
                redirects. Catch failures per file to continue processing a batch.
        """
        return upload_file(file_path, target, timeout)

    def upload_files(
        self,
        uploads: Sequence[tuple[str | Path, AttachmentUploadTarget]],
        *,
        max_workers: int = 4,
        timeout: float = 30.0,
    ) -> list[AttachmentUploadOutcome]:
        """Upload files concurrently and return one outcome per input, in order.

        Args:
            uploads: Pairs of local file paths and their corresponding targets.
                Each target must have a distinct attachment ID. An empty batch
                returns an empty list without network or runtime bridge calls.
            max_workers: Maximum concurrent uploads; defaults to 4. Set to 1 for
                sequential uploads. No more workers than files are started.
            timeout: Socket timeout per upload, in seconds; defaults to 30.

        Returns:
            Ordered outcomes carrying each input's attachment ID. A file failure
            does not stop the other uploads. Only successful outcomes should be
            referenced in findings or linked. Files remain owned by the caller.

        Raises:
            ActionFailure: Invalid batch shape, repeated attachment IDs, or an
                invalid worker count. The batch is rejected before any upload.
        """
        if (
            isinstance(max_workers, bool)
            or not isinstance(max_workers, int)
            or max_workers < 1
        ):
            raise ActionFailure("Upload max_workers must be a positive integer.")
        jobs = None
        with suppress(TypeError):
            jobs = list(uploads)
        if jobs is None or any(
            not isinstance(job, tuple | list)
            or len(job) != 2
            or not isinstance(job[0], str | Path)
            or not isinstance(job[1], AttachmentUploadTarget)
            for job in jobs
        ):
            raise ActionFailure(
                "Uploads require pairs of file paths and upload targets."
            )
        ids = [target.attachment_id for _, target in jobs]
        if len(set(ids)) != len(ids):
            raise ActionFailure("Upload targets must have distinct attachment IDs.")

        def upload_one(
            job: tuple[str | Path, AttachmentUploadTarget],
        ) -> AttachmentUploadOutcome:
            path, target = job
            try:
                receipt = self.upload_file(path, target, timeout=timeout)
            except AttachmentUploadError as error:
                return AttachmentUploadOutcome(
                    attachment_id=target.attachment_id,
                    file_name=target.file_name,
                    success=False,
                    error_code=error.error_code,
                    message=error.message,
                    status_code=error.status_code,
                )
            return AttachmentUploadOutcome(success=True, **receipt.model_dump())

        return parallel_map(upload_one, jobs, max_workers=max_workers)

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
