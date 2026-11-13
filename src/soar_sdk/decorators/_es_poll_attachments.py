"""Attachment preparation and queued association for direct ES polling."""

__lazy_modules__ = {
    "contextlib",
    "httpx",
    "importlib",
    "pathlib",
    "soar_sdk.abstract",
    "soar_sdk.models.finding",
    "tempfile",
    "typing",
    "uuid",
}

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.models.finding import Finding


def _reference_base_url(es_base_url: str) -> httpx.URL:
    """Obtain the deployment's provisional reference route from its bundle."""
    url = None
    with suppress(Exception):
        value = import_module("es_poll_api").get_attachment_reference_base_url()
        candidate = httpx.URL(value)
        origin = httpx.URL(es_base_url)
        if (
            (candidate.scheme, candidate.host, candidate.port)
            == (origin.scheme, origin.host, origin.port)
            and candidate.scheme in {"http", "https"}
            and candidate.host
            and not candidate.userinfo
            and not candidate.query
            and not candidate.fragment
        ):
            url = candidate
    if url is None:
        raise ValueError("Attachment reference route is unavailable.")
    return url


def _upload_poll_attachments(
    soar: SOARClient,
    findings: list[Finding],
    payloads: list[dict[str, Any]],
    es_base_url: str,
    used_ids: set[str],
) -> list[list[dict[str, Any]]]:
    """Upload bounded batches before creation, retaining only safe outcomes.

    Each reservation contains at most 20 files, the runtime service limit.
    Input order determines file/target ownership. The last successfully uploaded
    raw email is primary, matching the existing polling selection rule.
    """
    results: list[list[dict[str, Any]]] = [[] for _ in findings]
    files = [
        (index, attachment)
        for index, finding in enumerate(findings)
        for attachment in finding.attachments or []
    ]
    if not files:
        return results
    for index, finding in enumerate(findings):
        if finding.attachments:
            email = payloads[index].setdefault("email", {})
            email.pop("attachments", None)
            if any(item.is_raw_email for item in finding.attachments):
                email.pop("raw_email_link", None)

    # Reservation, filesystem and bundle failures must not discard the findings.
    # Do not retain upstream exception messages, signed URLs or file contents.
    completed = 0
    try:
        base_url = _reference_base_url(es_base_url)
        with TemporaryDirectory(prefix="soar-es-attachments-") as directory:
            for start in range(0, len(files), 20):
                chunk = files[start : start + 20]
                receipts = None
                with suppress(Exception):
                    targets = soar.attachments.get_upload_targets(
                        [attachment.file_name for _, attachment in chunk], str(uuid4())
                    )
                    ids = [str(UUID(target.attachment_id)) for target in targets]
                    if (
                        len(ids) != len(chunk)
                        or len(set(ids)) != len(ids)
                        or used_ids.intersection(ids)
                    ):
                        raise ValueError("Attachment IDs must be unique per run.")
                    used_ids.update(ids)
                    uploads = []
                    for offset, ((_, attachment), target) in enumerate(
                        zip(chunk, targets, strict=True)
                    ):
                        path = Path(directory) / str(start + offset)
                        try:
                            path.write_bytes(attachment.data)
                        except OSError:
                            # A missing path becomes a per-file upload failure;
                            # never upload a partially written file.
                            path = Path(directory) / f"missing-{start + offset}"
                        uploads.append((path, target))
                    receipts = soar.attachments.upload_files(uploads)
                for offset, (index, attachment) in enumerate(chunk):
                    receipt = None if receipts is None else receipts[offset]
                    entry: dict[str, Any] = {"success": False}
                    if receipt is None:
                        entry.update(
                            error_code="attachment_preparation",
                            message="Attachment upload preparation failed.",
                        )
                    else:
                        entry = receipt.model_dump(exclude_none=True)
                        if receipt.success:
                            reference = str(
                                base_url.copy_add_param(
                                    "attachment_id", receipt.attachment_id
                                )
                            )
                            email = payloads[index]["email"]
                            email.setdefault("attachments", []).append(
                                {
                                    "filename": attachment.file_name,
                                    "filesize": receipt.size_bytes,
                                    "url": reference,
                                }
                            )
                            if attachment.is_raw_email:
                                email["raw_email_link"] = reference
                    results[index].append(entry)
                    completed += 1
    except Exception:
        for index, _ in files[completed:]:
            results[index].append(
                {
                    "success": False,
                    "error_code": "attachment_preparation",
                    "message": "Attachment upload preparation failed.",
                }
            )
    return results


def _queue_poll_attachment_links(
    soar: SOARClient, results: list[dict[str, Any]]
) -> None:
    """Queue only successful finding/file pairs; an ACK is not persistence."""
    associations = []
    linked = []
    for result in results:
        ids = [
            attachment["attachment_id"]
            for attachment in result.get("attachments", [])
            if attachment["success"]
        ]
        if result["success"] and ids:
            associations.append(
                {"subject_id": result["finding_id"], "attachment_ids": ids}
            )
            linked.append(result)
    if not associations:
        return
    queued = False
    with suppress(Exception):
        soar.attachments.associate_subject_attachments(associations)
        queued = True
    for result, association in zip(linked, associations, strict=True):
        result["attachment_links"] = {
            "status": "queued" if queued else "failed",
            "attachment_ids": association["attachment_ids"],
        }
