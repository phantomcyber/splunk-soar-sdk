"""Bounded, byte-preserving analysis for untrusted RFC 5322 and MSG email."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from email import policy
from email.message import Message
from email.parser import BytesParser
from typing import cast

import extract_msg

from soar_sdk.extras.email.budget import (
    EmailAnalysisWarning,
    EmailBudgetLimits,
    EmailBudgetLimitType,
    EmailMessageBudget,
    warning_data,
)
from soar_sdk.extras.email.email_data import (
    MAX_MIME_DEPTH,
    EmailAttachment,
    EmailBody,
    EmailData,
    EmailHeaders,
    _decode_header_value,
    _decode_payload,
    _extract_urls_from_content,
    _get_charset,
    extract_email_headers,
)
from soar_sdk.models.container import Container
from soar_sdk.models.finding import Finding

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_MESSAGE_SUFFIXES = (".eml", ".msg")

INCOMPLETE_ANALYSIS_HEADLINE = (
    "Threat analysis incomplete: some email content was not analyzed."
)


@dataclass
class EmailAnalysisResult:
    """A fully staged email-analysis decision that is safe to persist."""

    root: EmailData | None
    root_raw: bytes | None
    reporter: EmailData | None
    fallback_metadata: dict[str, object]
    retained_attachments: list[EmailAttachment]
    warnings: list[EmailAnalysisWarning]
    projected_persisted_bytes: int

    @property
    def complete(self) -> bool:
        """Return whether all content under the selected root was analyzed."""
        return not self.warnings


@dataclass(frozen=True)
class _RootCandidate:
    filename: str
    content_type: str
    raw: bytes | None
    parsed: Message | None
    observed_size: int
    is_msg: bool


@dataclass
class _AnalysisAccumulator:
    plain_parts: list[str] = field(default_factory=list)
    html_parts: list[str] = field(default_factory=list)
    urls: set[str] = field(default_factory=set)
    attachments: list[EmailAttachment] = field(default_factory=list)
    retained: list[EmailAttachment] = field(default_factory=list)

    def add_body(self, content: str, *, is_html: bool) -> None:
        if is_html:
            self.html_parts.append(content)
        else:
            self.plain_parts.append(content)
        _extract_urls_from_content(content, self.urls, is_html=is_html)

    def body(self) -> EmailBody:
        return EmailBody(
            plain_text="\n".join(self.plain_parts) or None,
            html="\n".join(self.html_parts) or None,
        )


def _is_attachment(part: Message) -> bool:
    disposition = str(part.get("Content-Disposition") or "").lower()
    return bool(part.get_filename()) or "attachment" in disposition


def _looks_like_message(part: Message) -> bool:
    filename = (part.get_filename() or "").lower()
    return part.get_content_type() == "message/rfc822" or filename.endswith(
        _MESSAGE_SUFFIXES
    )


def _attachment_filename(part: Message) -> str:
    filename = part.get_filename() or "unnamed_attachment"
    return _decode_header_value(filename) or filename


def _encoded_payload_size(part: Message) -> int:
    """Return a non-underestimating decoded size without materializing the bytes."""
    payload = part.get_payload()
    if isinstance(payload, list):
        message_parts = cast(list[Message], payload)
        return sum(len(item.as_bytes(policy=policy.SMTP)) for item in message_parts)
    if isinstance(payload, bytes):
        return len(payload)
    if not isinstance(payload, str):
        return 0

    encoded = payload.encode("utf-8", errors="surrogateescape")
    transfer_encoding = str(part.get("Content-Transfer-Encoding") or "").lower()
    if transfer_encoding != "base64":
        return len(encoded)

    compact = re.sub(rb"\s+", b"", encoded)
    padding = min(2, len(compact) - len(compact.rstrip(b"=")))
    return max(0, ((len(compact) + 3) // 4) * 3 - padding)


def _decode_part(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="surrogateescape")
    return b""


def _message_bytes(part: Message) -> bytes:
    payload = part.get_payload()
    if isinstance(payload, list) and payload:
        return cast(list[Message], payload)[0].as_bytes(policy=policy.SMTP)
    return _decode_part(part)


def _parse_rfc_candidate(raw: bytes) -> Message | None:
    try:
        parsed = BytesParser().parsebytes(raw)
    except Exception:
        return None
    if not list(parsed.items()) and not parsed.is_multipart():
        return None
    return parsed


def _root_candidate(part: Message, limits: EmailBudgetLimits) -> _RootCandidate | None:
    if not _looks_like_message(part):
        return None

    filename = _attachment_filename(part)
    content_type = part.get_content_type()
    is_msg = filename.lower().endswith(".msg")
    observed_size = _encoded_payload_size(part)
    if observed_size > limits.max_raw_email_bytes:
        return _RootCandidate(
            filename=filename,
            content_type=content_type,
            raw=None,
            parsed=None,
            observed_size=observed_size,
            is_msg=is_msg,
        )

    raw = _message_bytes(part)
    observed_size = len(raw)
    if observed_size > limits.max_raw_email_bytes:
        return _RootCandidate(
            filename=filename,
            content_type=content_type,
            raw=None,
            parsed=None,
            observed_size=observed_size,
            is_msg=is_msg,
        )

    if is_msg:
        if not raw.startswith(_OLE2_MAGIC):
            return None
        return _RootCandidate(
            filename=filename,
            content_type=content_type,
            raw=raw,
            parsed=None,
            observed_size=observed_size,
            is_msg=True,
        )

    parsed = _parse_rfc_candidate(raw)
    if parsed is None:
        return None
    return _RootCandidate(
        filename=filename,
        content_type=content_type,
        raw=raw,
        parsed=parsed,
        observed_size=observed_size,
        is_msg=False,
    )


def _top_level_attachments(message: Message) -> list[Message]:
    """Return envelope attachments without descending into attached content."""
    attachments: list[Message] = []
    stack: list[tuple[Message, int]] = [(message, 0)]
    while stack:
        part, depth = stack.pop()
        if depth > MAX_MIME_DEPTH:
            raise ValueError(
                f"Email MIME nesting exceeds the supported depth of {MAX_MIME_DEPTH}"
            )
        if part is not message and _is_attachment(part):
            attachments.append(part)
            continue
        if not part.is_multipart():
            continue
        payload = part.get_payload()
        if isinstance(payload, list):
            message_parts = cast(list[Message], payload)
            stack.extend((child, depth + 1) for child in reversed(message_parts))
    return attachments


def _fallback_from_headers(
    headers: EmailHeaders, *, filename: str | None = None
) -> dict[str, object]:
    values: dict[str, object] = {
        "email_id": headers.email_id,
        "message_id": headers.message_id,
        "from": headers.from_address,
        "to": headers.to,
        "subject": headers.subject,
        "date": headers.date,
        "content_type": headers.content_type,
    }
    if filename is not None:
        values["filename"] = filename
    return {key: value for key, value in values.items() if value is not None}


def _metadata_only_result(
    *,
    observed_size: int,
    limits: EmailBudgetLimits,
    reporter: EmailData | None,
    fallback_metadata: dict[str, object],
    initial_warnings: list[EmailAnalysisWarning],
) -> EmailAnalysisResult:
    warnings = [
        *initial_warnings,
        EmailAnalysisWarning(
            code=EmailBudgetLimitType.RAW_EMAIL_BYTES,
            observed=observed_size,
            limit=limits.max_raw_email_bytes,
            scope="root",
            skipped_count=1,
        ),
    ]
    return EmailAnalysisResult(
        root=None,
        root_raw=None,
        reporter=reporter,
        fallback_metadata=fallback_metadata,
        retained_attachments=[],
        warnings=warnings,
        projected_persisted_bytes=0,
    )


def _rejection_reason(budget: EmailMessageBudget, decoded_size: int) -> str:
    if budget.attachment_count >= budget.limits.max_attachments:
        return EmailBudgetLimitType.ATTACHMENT_COUNT.value
    if decoded_size > budget.limits.max_attachment_bytes:
        return EmailBudgetLimitType.ATTACHMENT_BYTES.value
    return EmailBudgetLimitType.MESSAGE_ATTACHMENT_BYTES.value


def _record_decoded_attachment(
    *,
    filename: str,
    content_type: str | None,
    content_id: str | None,
    is_inline: bool,
    content: bytes,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
) -> None:
    accepted = budget.accept_attachment(filename, len(content))
    attachment = EmailAttachment(
        filename=filename,
        content_type=content_type,
        size=len(content),
        content_id=content_id,
        content=content if accepted and include_content else None,
        is_inline=is_inline,
        skip_reason=None if accepted else _rejection_reason(budget, len(content)),
    )
    accumulator.attachments.append(attachment)
    if accepted:
        accumulator.retained.append(attachment)


def _record_mime_attachment(
    part: Message,
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
) -> None:
    filename = _attachment_filename(part)
    estimated_size = _encoded_payload_size(part)
    preflight_rejects = (
        budget.attachment_count >= budget.limits.max_attachments
        or estimated_size > budget.limits.max_attachment_bytes
        or budget.attachment_bytes + estimated_size
        > budget.limits.max_message_attachment_bytes
    )
    if preflight_rejects:
        accepted = budget.accept_attachment(
            filename,
            0
            if budget.attachment_count >= budget.limits.max_attachments
            else estimated_size,
        )
        if accepted:  # pragma: no cover - guarded by the equivalent checks above
            raise AssertionError("attachment preflight and budget decision diverged")
        accumulator.attachments.append(
            EmailAttachment(
                filename=filename,
                content_type=part.get_content_type(),
                size=estimated_size,
                content_id=(part.get("Content-ID") or "").strip("<>") or None,
                is_inline="inline"
                in str(part.get("Content-Disposition") or "").lower(),
                skip_reason=_rejection_reason(budget, estimated_size),
            )
        )
        return

    _record_decoded_attachment(
        filename=filename,
        content_type=part.get_content_type(),
        content_id=(part.get("Content-ID") or "").strip("<>") or None,
        is_inline="inline" in str(part.get("Content-Disposition") or "").lower(),
        content=_decode_part(part),
        budget=budget,
        accumulator=accumulator,
        include_content=include_content,
    )


def _record_skipped_nested_message(
    part: Message,
    *,
    depth: int,
    accumulator: _AnalysisAccumulator,
) -> None:
    accumulator.attachments.append(
        EmailAttachment(
            filename=_attachment_filename(part),
            content_type=part.get_content_type(),
            size=_encoded_payload_size(part),
            content_id=(part.get("Content-ID") or "").strip("<>") or None,
            is_inline="inline" in str(part.get("Content-Disposition") or "").lower(),
            skip_reason=(f"{EmailBudgetLimitType.NESTED_EMAIL_DEPTH.value}:{depth}"),
        )
    )


def _record_body_part(part: Message, accumulator: _AnalysisAccumulator) -> None:
    content_type = part.get_content_type()
    if content_type not in {"text/plain", "text/html"}:
        return
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes) or not payload:
        return
    accumulator.add_body(
        _decode_payload(payload, _get_charset(part)),
        is_html=content_type == "text/html",
    )


def _walk_rfc_message(
    message: Message,
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
    nested_depth: int = 0,
) -> None:
    stack: list[tuple[Message, int, int, bool]] = [(message, 0, nested_depth, True)]
    while stack:
        part, mime_depth, current_nested_depth, is_root = stack.pop()
        if mime_depth > MAX_MIME_DEPTH:
            raise ValueError(
                f"Email MIME nesting exceeds the supported depth of {MAX_MIME_DEPTH}"
            )

        if not is_root and _looks_like_message(part):
            candidate = _root_candidate(part, budget.limits)
            if candidate is not None and candidate.raw is not None:
                next_depth = current_nested_depth + 1
                if not budget.accept_nested_depth(next_depth):
                    _record_skipped_nested_message(
                        part, depth=next_depth, accumulator=accumulator
                    )
                    continue
                if candidate.is_msg:
                    _walk_msg_bytes(
                        candidate.raw,
                        budget=budget,
                        accumulator=accumulator,
                        include_content=include_content,
                        nested_depth=next_depth,
                    )
                else:
                    stack.append(
                        (
                            cast(Message, candidate.parsed),
                            mime_depth + 1,
                            next_depth,
                            True,
                        )
                    )
                continue

        if not is_root and _is_attachment(part):
            _record_mime_attachment(
                part,
                budget=budget,
                accumulator=accumulator,
                include_content=include_content,
            )
            continue

        if part.is_multipart():
            payload = part.get_payload()
            if isinstance(payload, list):
                message_parts = cast(list[Message], payload)
                stack.extend(
                    (child, mime_depth + 1, current_nested_depth, False)
                    for child in reversed(message_parts)
                )
            continue

        _record_body_part(part, accumulator)


def _msg_headers(message: extract_msg.Message, email_id: str | None) -> EmailHeaders:
    date = message.date
    return EmailHeaders(
        email_id=email_id,
        message_id=message.messageId,
        to=message.to,
        from_address=message.sender,
        subject=message.subject,
        date=date.strftime("%a, %d %b %Y %H:%M:%S %z") if date else None,
        cc=message.cc,
        bcc=message.bcc,
        raw_headers=message.headerDict,
    )


def _msg_attachment_directories(message: extract_msg.MSGFile) -> list[str]:
    directories: list[str] = []
    for path in message.listDir(False, True, False):
        if path and path[0].startswith("__attach") and path[0] not in directories:
            directories.append(path[0])
    return directories


def _msg_attachment_fields(
    message: extract_msg.MSGFile, directory: str
) -> tuple[str, str | None, str | None]:
    filename = (
        message.getStringStream([directory, "__substg1.0_3707"])
        or message.getStringStream([directory, "__substg1.0_3704"])
        or "unnamed_attachment"
    )
    mimetype = message.getStringStream([directory, "__substg1.0_370E"])
    content_id = message.getStringStream([directory, "__substg1.0_3712"])
    return filename, mimetype, content_id


def _record_msg_stream_attachment(
    message: extract_msg.Message,
    directory: str,
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
) -> None:
    stream_path = [directory, "__substg1.0_37010102"]
    filename, mimetype, content_id = _msg_attachment_fields(message, directory)
    stream_size = message._getOleEntry(stream_path).size
    preflight_rejects = (
        budget.attachment_count >= budget.limits.max_attachments
        or stream_size > budget.limits.max_attachment_bytes
        or budget.attachment_bytes + stream_size
        > budget.limits.max_message_attachment_bytes
    )
    if preflight_rejects:
        accepted = budget.accept_attachment(
            filename,
            0
            if budget.attachment_count >= budget.limits.max_attachments
            else stream_size,
        )
        if accepted:  # pragma: no cover - guarded by the equivalent checks above
            raise AssertionError(
                "MSG attachment preflight and budget decision diverged"
            )
        accumulator.attachments.append(
            EmailAttachment(
                filename=filename,
                content_type=mimetype,
                size=stream_size,
                content_id=content_id,
                skip_reason=_rejection_reason(budget, stream_size),
            )
        )
        return

    _record_decoded_attachment(
        filename=filename,
        content_type=mimetype,
        content_id=content_id,
        is_inline=False,
        content=message.getStream(stream_path) or b"",
        budget=budget,
        accumulator=accumulator,
        include_content=include_content,
    )


def _walk_msg(
    message: extract_msg.Message,
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
    nested_depth: int,
) -> None:
    if message.body:
        accumulator.add_body(str(message.body), is_html=False)
    if message.htmlBody:
        html_body = message.htmlBody
        html_content = (
            html_body.decode("utf-8", errors="replace")
            if isinstance(html_body, bytes)
            else str(html_body)
        )
        accumulator.add_body(html_content, is_html=True)

    for directory in _msg_attachment_directories(message):
        stream_path = [directory, "__substg1.0_37010102"]
        if message.exists(stream_path):
            _record_msg_stream_attachment(
                message,
                directory,
                budget=budget,
                accumulator=accumulator,
                include_content=include_content,
            )
            continue

        attachment = message.initAttachmentFunc(message, directory)
        embedded_message = cast(extract_msg.Message, attachment.data)
        next_depth = nested_depth + 1
        if budget.accept_nested_depth(next_depth):
            _walk_msg(
                embedded_message,
                budget=budget,
                accumulator=accumulator,
                include_content=include_content,
                nested_depth=next_depth,
            )
        else:
            accumulator.attachments.append(
                EmailAttachment(
                    filename=_msg_attachment_fields(message, directory)[0],
                    content_type=attachment.mimetype,
                    skip_reason=(
                        f"{EmailBudgetLimitType.NESTED_EMAIL_DEPTH.value}:{next_depth}"
                    ),
                )
            )


def _walk_msg_bytes(
    raw: bytes,
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
    nested_depth: int,
) -> tuple[EmailHeaders, EmailBody, list[str]]:
    message = extract_msg.Message(raw, delayAttachments=True)
    try:
        headers = _msg_headers(message, None)
        _walk_msg(
            message,
            budget=budget,
            accumulator=accumulator,
            include_content=include_content,
            nested_depth=nested_depth,
        )
        return headers, accumulator.body(), sorted(accumulator.urls)
    finally:
        message.close()


def _record_extra_candidates(
    candidates: Sequence[_RootCandidate],
    *,
    budget: EmailMessageBudget,
    accumulator: _AnalysisAccumulator,
    include_content: bool,
) -> None:
    for candidate in candidates:
        if candidate.raw is None:
            accepted = budget.accept_attachment(
                candidate.filename, candidate.observed_size
            )
            if accepted:  # pragma: no cover - candidate exceeded the raw limit
                raise AssertionError("oversized root candidate unexpectedly accepted")
            accumulator.attachments.append(
                EmailAttachment(
                    filename=candidate.filename,
                    content_type=candidate.content_type,
                    size=candidate.observed_size,
                    skip_reason=_rejection_reason(budget, candidate.observed_size),
                )
            )
            continue
        _record_decoded_attachment(
            filename=candidate.filename,
            content_type=candidate.content_type,
            content_id=None,
            is_inline=False,
            content=candidate.raw,
            budget=budget,
            accumulator=accumulator,
            include_content=include_content,
        )


def _analyze_rfc_root(
    *,
    parsed: Message,
    raw: bytes,
    email_id: str | None,
    limits: EmailBudgetLimits,
    include_content: bool,
    extra_candidates: list[_RootCandidate],
) -> tuple[EmailData, list[EmailAttachment], list[EmailAnalysisWarning]]:
    budget = EmailMessageBudget(limits)
    accumulator = _AnalysisAccumulator()
    _walk_rfc_message(
        parsed,
        budget=budget,
        accumulator=accumulator,
        include_content=include_content,
    )
    _record_extra_candidates(
        extra_candidates,
        budget=budget,
        accumulator=accumulator,
        include_content=include_content,
    )

    body = accumulator.body()
    root = EmailData(
        raw_email=raw.decode("utf-8", errors="replace"),
        headers=extract_email_headers(parsed, email_id),
        body=body,
        urls=sorted(accumulator.urls),
        attachments=accumulator.attachments,
    )
    return root, accumulator.retained, budget.warnings


def _analyze_msg_root(
    *,
    raw: bytes,
    email_id: str | None,
    limits: EmailBudgetLimits,
    include_content: bool,
    extra_candidates: list[_RootCandidate],
) -> tuple[EmailData, list[EmailAttachment], list[EmailAnalysisWarning]]:
    budget = EmailMessageBudget(limits)
    accumulator = _AnalysisAccumulator()
    message = extract_msg.Message(raw, delayAttachments=True)
    try:
        headers = _msg_headers(message, email_id)
        _walk_msg(
            message,
            budget=budget,
            accumulator=accumulator,
            include_content=include_content,
            nested_depth=0,
        )
        _record_extra_candidates(
            extra_candidates,
            budget=budget,
            accumulator=accumulator,
            include_content=include_content,
        )
        root = EmailData(
            raw_email=raw.decode("utf-8", errors="replace"),
            headers=headers,
            body=accumulator.body(),
            urls=sorted(accumulator.urls),
            attachments=accumulator.attachments,
        )
        return root, accumulator.retained, budget.warnings
    finally:
        message.close()


def _reporter_data(message: Message, raw: bytes, email_id: str | None) -> EmailData:
    accumulator = _AnalysisAccumulator()
    _record_body_part(message, accumulator)
    if message.is_multipart():
        payload = message.get_payload()
        if isinstance(payload, list):
            for part in cast(list[Message], payload):
                if not _is_attachment(part) and not part.is_multipart():
                    _record_body_part(part, accumulator)
    return EmailData(
        raw_email="",
        headers=extract_email_headers(message, email_id),
        body=accumulator.body(),
        urls=sorted(accumulator.urls),
        attachments=[],
    )


def analyze_email(
    raw_email: str | bytes,
    *,
    limits: EmailBudgetLimits,
    email_id: str | None = None,
    include_attachment_content: bool = True,
) -> EmailAnalysisResult:
    """Select an analysis root and stage only content accepted by finite budgets."""
    limits.validate()
    raw_bytes = raw_email.encode("utf-8") if isinstance(raw_email, str) else raw_email

    initial_warnings: list[EmailAnalysisWarning] = []
    reporter: EmailData | None = None
    extra_candidates: list[_RootCandidate] = []

    if raw_bytes.startswith(_OLE2_MAGIC):
        if len(raw_bytes) > limits.max_raw_email_bytes:
            return _metadata_only_result(
                observed_size=len(raw_bytes),
                limits=limits,
                reporter=None,
                fallback_metadata={"email_id": email_id, "format": "msg"},
                initial_warnings=[],
            )
        root_raw = raw_bytes
        root_is_msg = True
        root_parsed = None
    else:
        envelope = BytesParser().parsebytes(raw_bytes)
        declared_candidates = [
            candidate
            for part in _top_level_attachments(envelope)
            if (candidate := _root_candidate(part, limits)) is not None
        ]
        if declared_candidates:
            selected = declared_candidates[0]
            reporter = _reporter_data(envelope, raw_bytes, email_id)
            extra_candidates = declared_candidates[1:]
            if len(declared_candidates) > 1:
                initial_warnings.append(
                    EmailAnalysisWarning(
                        code=EmailBudgetLimitType.MULTIPLE_ROOT_CANDIDATES,
                        observed=len(declared_candidates),
                        limit=1,
                        scope="envelope",
                        skipped_count=len(declared_candidates) - 1,
                    )
                )
            if selected.raw is None:
                return _metadata_only_result(
                    observed_size=selected.observed_size,
                    limits=limits,
                    reporter=reporter,
                    fallback_metadata={
                        "email_id": email_id,
                        "filename": selected.filename,
                        "content_type": selected.content_type,
                    },
                    initial_warnings=initial_warnings,
                )
            root_raw = selected.raw
            root_is_msg = selected.is_msg
            root_parsed = selected.parsed
        else:
            root_raw = raw_bytes
            root_is_msg = False
            root_parsed = envelope

        if len(root_raw) > limits.max_raw_email_bytes:
            headers = extract_email_headers(cast(Message, root_parsed), email_id)
            return _metadata_only_result(
                observed_size=len(root_raw),
                limits=limits,
                reporter=reporter,
                fallback_metadata=_fallback_from_headers(headers),
                initial_warnings=initial_warnings,
            )

    if root_is_msg:
        root, retained, budget_warnings = _analyze_msg_root(
            raw=root_raw,
            email_id=email_id,
            limits=limits,
            include_content=include_attachment_content,
            extra_candidates=extra_candidates,
        )
    else:
        if root_parsed is None:  # pragma: no cover - non-MSG candidates always parse
            raise AssertionError("RFC 5322 root is missing its parsed message")
        root, retained, budget_warnings = _analyze_rfc_root(
            parsed=root_parsed,
            raw=root_raw,
            email_id=email_id,
            limits=limits,
            include_content=include_attachment_content,
            extra_candidates=extra_candidates,
        )

    projected_attachment_bytes = (
        sum(attachment.size for attachment in retained)
        if include_attachment_content
        else 0
    )
    return EmailAnalysisResult(
        root=root,
        root_raw=root_raw,
        reporter=reporter,
        fallback_metadata={},
        retained_attachments=retained,
        warnings=[*initial_warnings, *budget_warnings],
        projected_persisted_bytes=len(root_raw) + projected_attachment_bytes,
    )


def _warning_description(
    original: str | None, warnings: Sequence[EmailAnalysisWarning]
) -> str:
    warning_text = "\n".join(warning.user_message() for warning in warnings)
    prefix = f"{INCOMPLETE_ANALYSIS_HEADLINE}\n{warning_text}"
    return f"{prefix}\n\n{original}" if original else prefix


def _warning_artifact(warning: EmailAnalysisWarning) -> dict[str, object]:
    return {
        "name": "Email Analysis Warning",
        "label": "event",
        "cef": {
            "analysisComplete": False,
            "analysisLimitType": warning.code.value,
            "analysisObserved": warning.observed,
            "analysisLimit": warning.limit,
            "analysisScope": warning.scope,
            "analysisFilename": warning.filename,
            "analysisSkippedCount": warning.skipped_count,
        },
    }


def apply_warnings_to_container(
    container: Container, warnings: Sequence[EmailAnalysisWarning]
) -> None:
    """Expose incomplete analysis in a SOAR container and warning artifacts."""
    if not warnings:
        return
    container.description = _warning_description(container.description, warnings)
    container.data = {
        **(container.data or {}),
        "email_analysis": warning_data(list(warnings)),
    }
    container.artifacts = [
        *(container.artifacts or []),
        *(_warning_artifact(warning) for warning in warnings),
    ]


def apply_warnings_to_finding(
    finding: Finding, warnings: Sequence[EmailAnalysisWarning]
) -> None:
    """Expose incomplete analysis in an ES finding without changing its identity."""
    if not warnings:
        return
    finding.rule_description = _warning_description(finding.rule_description, warnings)
    finding.additional_fields = {
        **(finding.additional_fields or {}),
        "email_analysis": warning_data(list(warnings)),
    }
