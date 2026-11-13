"""Direct ES polling, independent of classic SOAR container and vault APIs."""

__lazy_modules__ = {
    "asyncio",
    "contextlib",
    "copy",
    "soar_sdk.abstract",
    "soar_sdk.action_results",
    "soar_sdk.app",
    "soar_sdk.decorators._es_poll_attachments",
    "soar_sdk.models.finding",
    "soar_sdk.params",
    "typing",
}

import asyncio
from contextlib import suppress
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.decorators._es_poll_attachments import (
    _queue_poll_attachment_links,
    _upload_poll_attachments,
)
from soar_sdk.models.finding import Finding
from soar_sdk.params import OnESPollParams

if TYPE_CHECKING:
    from soar_sdk.app import App


def _run_direct_es_poll(
    app: "App",
    generator: Any,  # noqa: ANN401
    params: OnESPollParams,
    soar: SOARClient,
    *,
    is_async: bool,
) -> bool:
    """Consume findings, report each outcome, and never create SOAR containers."""
    results: list[dict[str, Any]] = []
    batch: list[tuple[int, Any]] = []
    ingest = app._es_ingest_config
    state = app.asset._ingest_state
    polling_failed = False
    batch_failed = False
    count = 0
    used_attachment_ids: set[str] = set()
    attachment_count = 0

    def flush() -> bool:
        nonlocal attachment_count, batch_failed
        if not batch:
            return True
        start = len(results)
        payloads = []
        indexes = []
        findings = []
        for index, item in batch:
            message = None
            payload = None
            if not isinstance(item, Finding):
                message = "ES polling must yield Finding objects."
            else:
                with suppress(ValueError):
                    payload = item.to_dict()
            if payload is None:
                results.append(
                    {
                        "index": index,
                        "success": False,
                        "error_code": "validation",
                        "message": message or "Invalid ES finding payload.",
                    }
                )
                continue
            for field in (
                "security_domain",
                "urgency",
                "investigation_type",
                "drilldown_searches",
                "drilldown_dashboards",
            ):
                if field not in payload and ingest.get("es_" + field) is not None:
                    payload[field] = ingest["es_" + field]
            for field in ("run_threat_analysis", "launch_automation"):
                if not payload.get(field):
                    payload[field] = ingest.get("es_" + field, False)
            payload.setdefault("finding_source", str(app.app_meta_info.get("name", "")))
            payloads.append(payload)
            indexes.append(index)
            findings.append(item)
        if payloads:
            attachments = _upload_poll_attachments(
                soar, findings, payloads, params.base_url or "", used_attachment_ids
            )
            response = soar.create_findings_bulk(payloads)
            batch_results = []
            for result in response["results"]:
                position = result["index"]
                entry = {**result, "index": indexes[position]}
                if attachments[position]:
                    entry["attachments"] = attachments[position]
                batch_results.append(entry)
            _queue_poll_attachment_links(soar, batch_results)
            results.extend(batch_results)
        batch.clear()
        attachment_count = 0
        batch_failed = any(not result["success"] for result in results[start:])
        if not batch_failed and state is not None:
            state.commit()
            state.begin_transaction()
        return not batch_failed

    try:
        if state is not None:
            state.begin_transaction()
        while not params.container_count or count < params.container_count:
            checkpoint = deepcopy(state.get_all()) if state is not None else {}
            try:
                item = (
                    asyncio.run(generator.asend(None))
                    if is_async
                    else generator.send(None)
                )
            except (StopIteration, StopAsyncIteration):
                break
            file_count = len(item.attachments or []) if isinstance(item, Finding) else 0
            if batch and attachment_count + file_count > 20:
                # Reading the next finding can advance its source cursor. Commit
                # only the previous batch, then restore the lookahead's state.
                if state is not None:
                    next_state = state.get_all()
                    state.put_all(checkpoint)
                if not flush():
                    break
                if state is not None:
                    state.put_all(next_state)
            batch.append((count, item))
            attachment_count += file_count
            count += 1
            if len(batch) == soar.MAX_BULK_FINDINGS and not flush():
                break
        if not batch_failed:
            flush()
    except Exception:
        # Handler exceptions can contain credentials or message contents.
        polling_failed = True
    finally:
        try:
            if is_async:
                asyncio.run(generator.aclose())
            else:
                generator.close()
        except Exception:
            polling_failed = True
        if state is not None and state.in_transaction:
            try:
                if polling_failed or batch_failed:
                    state.rollback()
                else:
                    # Save trailing handler changes only after successful batches.
                    state.commit()
            except Exception:
                polling_failed = True
                with suppress(Exception):
                    state.rollback()

    results.sort(key=lambda result: result["index"])
    created = sum(result["success"] for result in results)
    failed = len(results) - created
    attachments = [item for result in results for item in result.get("attachments", [])]
    uploaded = sum(item["success"] for item in attachments)
    upload_failed = len(attachments) - uploaded
    links = [
        result["attachment_links"] for result in results if "attachment_links" in result
    ]
    links_queued = sum(
        len(link["attachment_ids"]) for link in links if link["status"] == "queued"
    )
    links_failed = sum(
        len(link["attachment_ids"]) for link in links if link["status"] == "failed"
    )
    status = (
        "error"
        if polling_failed or (failed and not created)
        else "partial"
        if failed or upload_failed or links_failed
        else "success"
    )
    result = ActionResult(
        status=status != "error",
        message=f"ES polling {status}: {created} created, {failed} failed.",
        param=params.model_dump(),
    )
    for outcome in results:
        result.add_data(outcome)
    result.set_summary(
        {
            "status": status,
            "created": created,
            "failed": failed,
            "polling_failed": polling_failed,
            "attachments_uploaded": uploaded,
            "attachments_failed": upload_failed,
            "links_queued": links_queued,
            "links_failed": links_failed,
        }
    )
    return app._adapt_action_result(result, app.actions_manager)
