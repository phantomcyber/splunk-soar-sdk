"""Direct ES polling, independent of classic SOAR container and vault APIs."""

__lazy_modules__ = {
    "asyncio",
    "contextlib",
    "copy",
    "httpx",
    "sys",
    "soar_sdk.abstract",
    "soar_sdk.action_results",
    "soar_sdk.app",
    "soar_sdk.exceptions",
    "soar_sdk.decorators._es_poll_attachments",
    "soar_sdk.decorators._es_poll_preparation",
    "soar_sdk.models.finding",
    "soar_sdk.logging",
    "soar_sdk.params",
    "time",
    "typing",
}

import asyncio
import sys
from contextlib import suppress
from copy import deepcopy
from time import sleep
from typing import TYPE_CHECKING, Any

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.decorators._es_poll_attachments import (
    _queue_poll_attachment_links,
    _upload_poll_attachments,
)
from soar_sdk.decorators._es_poll_preparation import (
    _default_finding_source,
    _finding_default_updates,
)
from soar_sdk.exceptions import ActionFailure, FindingAPIError
from soar_sdk.logging import getLogger
from soar_sdk.models.finding import Finding
from soar_sdk.params import OnESPollParams

if TYPE_CHECKING:
    from soar_sdk.app import App


def _poll_error_details(stage: str, error: Exception) -> dict[str, str | int]:
    """Describe a polling failure without exception text or dynamic class names."""
    error_type = next(
        kind.__name__
        for kind in (
            httpx.HTTPStatusError,
            httpx.TimeoutException,
            httpx.TransportError,
            FindingAPIError,
            ActionFailure,
            TimeoutError,
            ConnectionError,
            KeyError,
            TypeError,
            ValueError,
            RuntimeError,
            OSError,
            Exception,
        )
        if isinstance(error, kind)
    )
    details: dict[str, str | int] = {"stage": stage, "error_type": error_type}
    with suppress(Exception):
        status = getattr(error, "status_code", None)
        if status is None:
            status = getattr(getattr(error, "response", None), "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            details["status_code"] = status
    # LB state storage uses gRPC, but classic SOAR does not require grpcio.
    # Read only a recognized status enum, never details(), debug strings or args.
    grpc = sys.modules.get("grpc")
    if grpc is not None and isinstance(error, getattr(grpc, "RpcError", ())):
        details["error_type"] = "RpcError"
        with suppress(Exception):
            code = error.code().name
            if code in {
                "CANCELLED",
                "UNKNOWN",
                "INVALID_ARGUMENT",
                "DEADLINE_EXCEEDED",
                "NOT_FOUND",
                "ALREADY_EXISTS",
                "PERMISSION_DENIED",
                "RESOURCE_EXHAUSTED",
                "FAILED_PRECONDITION",
                "ABORTED",
                "OUT_OF_RANGE",
                "UNIMPLEMENTED",
                "INTERNAL",
                "UNAVAILABLE",
                "DATA_LOSS",
                "UNAUTHENTICATED",
            }:
                details["rpc_code"] = code
    return details


def _create_poll_findings(
    soar: SOARClient, payloads: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Retry failed creates in memory without reserving or uploading files again.

    A timeout or lost response can hide a successful create, so these bounded
    retries can create duplicate findings. Successful results are never replayed.
    """
    results = soar.create_findings_bulk(payloads)["results"]
    for delay in (1, 2):
        pending = [
            index
            for index, result in enumerate(results)
            if not result["success"]
            and result.get("error_code") in {"rate_limit", "unavailable", "timeout"}
        ]
        if not pending:
            break
        sleep(delay)
        retried = soar.create_findings_bulk([payloads[index] for index in pending])
        for result in retried["results"]:
            index = pending[result["index"]]
            results[index] = {**result, "index": index}
    return results


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
    polling_errors: list[dict[str, str | int]] = []
    stage = "state_begin"
    count = 0
    used_attachment_ids: set[str] = set()
    attachment_count = 0
    finding_source = _default_finding_source(
        str(app.app_meta_info.get("name", "")), app._asset_name
    )

    def record_error(error_stage: str, error: Exception) -> None:
        details = _poll_error_details(error_stage, error)
        polling_errors.append(details)
        getLogger().error(
            "ES polling failure: stage=%s error_type=%s status_code=%s rpc_code=%s "
            "findings_accepted=%s findings_recorded=%s pending_findings=%s",
            details["stage"],
            details["error_type"],
            details.get("status_code"),
            details.get("rpc_code"),
            count,
            len(results),
            len(batch),
        )

    def flush() -> None:
        nonlocal attachment_count, stage
        if not batch:
            return
        stage = "prepare_findings"
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
            payload.update(_finding_default_updates(payload, ingest, finding_source))
            # Association needs the future finding ID, and its queue ACK does
            # not make attachments readable. Reject before allocating files
            # until the integration supplies a readiness guarantee.
            if item.attachments and (
                payload["run_threat_analysis"] or payload["launch_automation"]
            ):
                results.append(
                    {
                        "index": index,
                        "success": False,
                        "error_code": "attachment_readiness",
                        "message": (
                            "Immediate threat analysis or automation is unavailable "
                            "for findings with local attachments until attachment "
                            "readiness is guaranteed. Disable both flags to create "
                            "the finding."
                        ),
                    }
                )
                continue
            payloads.append(payload)
            indexes.append(index)
            findings.append(item)
        if payloads:
            stage = "upload_attachments"
            attachments = _upload_poll_attachments(
                soar, findings, payloads, params.base_url or "", used_attachment_ids
            )
            stage = "create_findings"
            response = _create_poll_findings(soar, payloads)
            stage = "process_response"
            batch_results = []
            for result in response:
                position = result["index"]
                entry = {**result, "index": indexes[position]}
                if attachments[position]:
                    entry["attachments"] = attachments[position]
                batch_results.append(entry)
            stage = "associate_attachments"
            _queue_poll_attachment_links(soar, batch_results)
            results.extend(batch_results)
        batch.clear()
        attachment_count = 0
        # Source messages have been processed even when ES rejects their findings.
        # Persist their staged cursors so a poison message cannot block later mail.
        if state is not None:
            stage = "state_commit"
            state.commit()
            stage = "state_begin"
            state.begin_transaction()
        for outcome in results[start:]:
            if not outcome["success"]:
                getLogger().warning(
                    "ES polling skipped finding at index %s (error_code=%s, "
                    "status_code=%s); continuing without replay after checkpoint.",
                    outcome["index"],
                    outcome.get("error_code"),
                    outcome.get("status_code"),
                )

    try:
        if state is not None:
            state.begin_transaction()
        while not params.container_count or count < params.container_count:
            stage = "state_read"
            checkpoint = deepcopy(state.get_all()) if state is not None else {}
            try:
                stage = "poll"
                item = (
                    asyncio.run(generator.asend(None))
                    if is_async
                    else generator.send(None)
                )
            except (StopIteration, StopAsyncIteration):
                break
            stage = "read_finding"
            file_count = len(item.attachments or []) if isinstance(item, Finding) else 0
            if batch and attachment_count + file_count > 20:
                # Reading the next finding can advance its source cursor. Commit
                # only the previous batch, then restore the lookahead's state.
                if state is not None:
                    stage = "state_read"
                    next_state = state.get_all()
                    stage = "state_restore"
                    state.put_all(checkpoint)
                flush()
                if state is not None:
                    stage = "state_restore"
                    state.put_all(next_state)
            batch.append((count, item))
            attachment_count += file_count
            count += 1
            if len(batch) == soar.MAX_BULK_FINDINGS:
                flush()
        flush()
    except Exception as error:
        # Handler exceptions can contain credentials or message contents.
        polling_failed = True
        record_error(stage, error)
    finally:
        try:
            if is_async:
                asyncio.run(generator.aclose())
            else:
                generator.close()
        except Exception as error:
            polling_failed = True
            record_error("generator_close", error)
        if state is not None and state.in_transaction:
            try:
                if polling_failed:
                    stage = "state_rollback"
                    state.rollback()
                else:
                    # Save trailing source progress, including skipped messages.
                    stage = "state_commit"
                    state.commit()
            except Exception as error:
                polling_failed = True
                record_error(stage, error)
                try:
                    state.rollback()
                except Exception as rollback_error:
                    record_error("state_rollback", rollback_error)

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
    message = f"ES polling {status}: {created} created, {failed} failed."
    if polling_errors:
        first = polling_errors[0]
        message += f" stage={first['stage']} error_type={first['error_type']}"
        if "status_code" in first:
            message += f" status_code={first['status_code']}"
        if "rpc_code" in first:
            message += f" rpc_code={first['rpc_code']}"
    result = ActionResult(
        status=status != "error",
        message=message,
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
            **({"polling_errors": polling_errors} if polling_errors else {}),
        }
    )
    return app._adapt_action_result(result, app.actions_manager)
