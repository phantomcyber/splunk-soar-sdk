"""Shared finding preparation, independent of polling transports and storage."""

__lazy_modules__ = {
    "collections.abc",
    "soar_sdk.models.finding",
    "typing",
}

from collections.abc import Mapping, MutableMapping
from typing import Any

from soar_sdk.models.finding import FindingAttachment

_INGEST_METADATA_FIELDS = (
    "security_domain",
    "urgency",
    "investigation_type",
    "drilldown_searches",
    "drilldown_dashboards",
)
_INGEST_BOOLEAN_FIELDS = ("run_threat_analysis", "launch_automation")
_FINDING_DEFAULT_FIELDS = (
    *_INGEST_METADATA_FIELDS,
    *_INGEST_BOOLEAN_FIELDS,
    "finding_source",
)


def _default_finding_source(app_name: str, asset_name: str) -> str:
    """Preserve the classic asset-qualified source and its name fallbacks."""
    return (
        f"{app_name} - {asset_name}"
        if app_name and asset_name
        else app_name or asset_name
    )


def _finding_default_updates(
    current: Mapping[str, Any], ingest: Mapping[str, Any], finding_source: str
) -> dict[str, Any]:
    """Select defaults while preserving explicit metadata and source values.

    False analysis/automation flags retain their existing ingest-default
    fallback. Callers normalize transport-specific drilldown representations.
    """
    updates = {}
    for field in _INGEST_METADATA_FIELDS:
        if current.get(field) is None and ingest.get("es_" + field) is not None:
            updates[field] = ingest["es_" + field]
    for field in _INGEST_BOOLEAN_FIELDS:
        if not current.get(field):
            updates[field] = ingest.get("es_" + field, False)
    if current.get("finding_source") is None and finding_source:
        updates["finding_source"] = finding_source
    return updates


def _add_uploaded_attachment(
    email: MutableMapping[str, Any],
    attachment: FindingAttachment,
    reference: str,
    size_bytes: int | None,
) -> None:
    """Append successful file metadata and select the last successful raw email."""
    email.setdefault("attachments", []).append(
        {"filename": attachment.file_name, "filesize": size_bytes, "url": reference}
    )
    if attachment.is_raw_email:
        email["raw_email_link"] = reference
