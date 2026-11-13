"""Stream presigned multipart uploads without credential-bearing HTTP logs."""

__lazy_modules__ = {
    "collections.abc",
    "contextlib",
    "datetime",
    "http.client",
    "math",
    "os",
    "pathlib",
    "typing",
    "urllib.parse",
    "uuid",
    "soar_sdk.exceptions",
    "soar_sdk.models.attachment_upload",
}

from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from math import isfinite
from os import fstat
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit
from uuid import uuid4

from soar_sdk.exceptions import AttachmentUploadError
from soar_sdk.models.attachment_upload import (
    AttachmentUploadResult,
    AttachmentUploadTarget,
)


def _quoted(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _multipart_prefix(target: AttachmentUploadTarget, boundary: str) -> bytes:
    parts = []
    for field in target.form_fields:
        if field.name == "file":
            raise ValueError
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{_quoted(field.name)}"\r\n\r\n'
            f"{field.value.get_secret_value()}\r\n"
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{_quoted(target.file_name)}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    )
    return "".join(parts).encode("utf-8")


def _body(file: BinaryIO, size: int, prefix: bytes, suffix: bytes) -> Iterator[bytes]:
    yield prefix
    remaining = size
    while remaining:
        chunk = file.read(min(remaining, 64 * 1024))
        if not chunk:
            raise OSError("Attachment file changed during upload.")
        remaining -= len(chunk)
        yield chunk
    if file.read(1):
        raise OSError("Attachment file changed during upload.")
    yield suffix


def upload_file(
    file_path: str | Path, target: AttachmentUploadTarget, timeout: float
) -> AttachmentUploadResult:
    """Upload one file, retaining only safe metadata on failure."""
    connection = None
    attachment_id = (
        target.attachment_id if isinstance(target, AttachmentUploadTarget) else None
    )
    code, message, status = "validation", "Invalid attachment upload inputs.", None
    try:
        if not isinstance(target, AttachmentUploadTarget):
            raise ValueError
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int | float)
            or not isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError
        url = urlsplit(target.upload_url.get_secret_value())
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.fragment
        ):
            raise ValueError
        port = url.port
        request_path = url.path or "/"
        if url.query:
            request_path += "?" + url.query
        request_path.encode("ascii")
        boundary = uuid4().hex
        prefix = _multipart_prefix(target, boundary)
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        path = Path(file_path)
        if target.expires_at <= datetime.now(UTC):
            code, message = "expired", "Attachment upload target has expired."
        else:
            code, message = "file", "Unable to read the attachment file."
            if not path.is_file():
                raise OSError("Attachment must be a regular file.")
            with path.open("rb") as file:
                size = fstat(file.fileno()).st_size
                if size > target.max_size_bytes:
                    code, message = (
                        "validation",
                        "Attachment exceeds the upload target's maximum size.",
                    )
                else:
                    code, message = (
                        "unavailable",
                        "Attachment upload service is unavailable.",
                    )
                    connection_type = (
                        HTTPSConnection if url.scheme == "https" else HTTPConnection
                    )
                    connection = connection_type(url.hostname, port, timeout=timeout)
                    connection.set_debuglevel(0)
                    connection.request(
                        "POST",
                        request_path,
                        body=_body(file, size, prefix, suffix),
                        headers={
                            "Content-Type": f"multipart/form-data; boundary={boundary}",
                            "Content-Length": str(len(prefix) + size + len(suffix)),
                        },
                    )
                    status = connection.getresponse().status
                    if status in {200, 201, 204}:
                        return AttachmentUploadResult(
                            attachment_id=target.attachment_id,
                            file_name=target.file_name,
                            size_bytes=size,
                        )
                    if status in {401, 403}:
                        code, message = (
                            "authorization",
                            "Attachment upload was not authorized.",
                        )
                    elif 400 <= status < 500:
                        code, message = "rejected", "Attachment upload was rejected."
                    elif status >= 500:
                        code, message = (
                            "unavailable",
                            "Attachment upload service is unavailable.",
                        )
                    else:
                        code, message = (
                            "response",
                            "Unexpected attachment upload response.",
                        )
    except TimeoutError:
        code, message = "timeout", "Attachment upload timed out."
    except (ValueError, TypeError, OverflowError):
        # Discard errors that may include signed URLs, form values or file paths.
        pass
    except (OSError, HTTPException):
        pass
    finally:
        if connection is not None:
            with suppress(OSError):
                connection.close()
    # Raise outside handlers so neither __cause__ nor __context__ retains secrets.
    raise AttachmentUploadError(message, code, attachment_id, status)
