"""Behavioral contract for safe email-root selection and warning presentation."""

from __future__ import annotations

from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from unittest.mock import MagicMock, patch

import pytest

from soar_sdk.extras.email import analysis
from soar_sdk.extras.email.analysis import (
    INCOMPLETE_ANALYSIS_HEADLINE,
    analyze_email,
    apply_warnings_to_container,
    apply_warnings_to_finding,
)
from soar_sdk.extras.email.budget import (
    EmailAnalysisWarning,
    EmailBudgetLimits,
    EmailBudgetLimitType,
    EmailMessageBudget,
)
from soar_sdk.models.container import Container
from soar_sdk.models.finding import Finding
from tests.extras.email.fixtures import (
    AttachmentFixture,
    make_attachment_flood,
    make_email,
    make_nested_report,
    make_report_envelope,
)


def _limits(**overrides: int) -> EmailBudgetLimits:
    values = {
        "max_raw_email_bytes": 1024 * 1024,
        "max_attachment_bytes": 16,
        "max_message_attachment_bytes": 32,
        "max_attachments": 100,
        "max_nested_email_depth": 10,
        "max_poll_bytes": 1024 * 1024 + 32,
    }
    values.update(overrides)
    return EmailBudgetLimits(**values)


def test_direct_message_below_all_limits_is_complete() -> None:
    payload = b"evidence"
    raw = make_email(
        attachments=[AttachmentFixture("evidence.txt", payload, "text", "plain")]
    )

    result = analyze_email(raw, limits=_limits())

    assert result.complete
    assert result.root is not None
    assert result.root.headers.subject == "Direct message"
    assert result.root_raw == raw
    assert result.reporter is None
    assert result.fallback_metadata == {}
    assert [attachment.filename for attachment in result.retained_attachments] == [
        "evidence.txt"
    ]
    assert result.retained_attachments[0].content == payload
    assert "skip_reason" not in result.root.to_dict()["attachments"][0]
    assert result.warnings == []
    assert result.projected_persisted_bytes == len(raw) + len(payload)


def test_per_attachment_limit_accepts_equal_and_skips_one_byte_over() -> None:
    at_limit = b"a" * 16
    over_limit = b"b" * 17
    raw = make_email(
        subject="Attachment boundaries",
        attachments=[
            AttachmentFixture("at-limit.bin", at_limit),
            AttachmentFixture("over-limit.bin", over_limit),
        ],
    )

    result = analyze_email(raw, limits=_limits())

    assert not result.complete
    assert [attachment.filename for attachment in result.retained_attachments] == [
        "at-limit.bin"
    ]
    assert result.projected_persisted_bytes == len(raw) + len(at_limit)
    assert [(warning.code, warning.filename) for warning in result.warnings] == [
        (EmailBudgetLimitType.ATTACHMENT_BYTES, "over-limit.bin")
    ]


def test_aggregate_limit_retains_deterministic_prefix() -> None:
    raw = make_email(
        subject="Aggregate boundary",
        attachments=[
            AttachmentFixture("first.bin", b"a" * 12),
            AttachmentFixture("second.bin", b"b" * 12),
            AttachmentFixture("third.bin", b"c" * 9),
        ],
    )

    result = analyze_email(
        raw,
        limits=_limits(max_attachment_bytes=20, max_message_attachment_bytes=32),
    )

    assert [attachment.filename for attachment in result.retained_attachments] == [
        "first.bin",
        "second.bin",
    ]
    assert result.warnings[0].code is EmailBudgetLimitType.MESSAGE_ATTACHMENT_BYTES
    assert result.warnings[0].filename == "third.bin"
    assert result.warnings[0].skipped_count == 1


def test_attachment_count_flood_retains_first_hundred() -> None:
    raw = make_attachment_flood()

    result = analyze_email(
        raw,
        limits=_limits(
            max_raw_email_bytes=2 * 1024 * 1024,
            max_attachment_bytes=2,
            max_message_attachment_bytes=200,
            max_attachments=100,
            max_poll_bytes=2 * 1024 * 1024 + 200,
        ),
    )

    assert len(result.retained_attachments) == 100
    assert result.retained_attachments[0].filename == "attachment-000.bin"
    assert result.retained_attachments[-1].filename == "attachment-099.bin"
    assert len(result.warnings) == 1
    assert result.warnings[0].code is EmailBudgetLimitType.ATTACHMENT_COUNT
    assert result.warnings[0].filename == "attachment-100.bin"
    assert result.warnings[0].skipped_count == 1


def test_single_attached_email_becomes_analysis_root() -> None:
    payload = b"evidence"
    phishing = make_email(
        subject="Credential harvesting lure",
        sender="criminal@example.test",
        attachments=[AttachmentFixture("evidence.txt", payload, "text", "plain")],
    )
    envelope = make_report_envelope([("reported-phish.eml", phishing)])

    result = analyze_email(envelope, limits=_limits())

    assert result.complete
    assert result.root is not None
    assert result.root.headers.subject == "Credential harvesting lure"
    assert result.root.headers.from_address == "criminal@example.test"
    assert result.root_raw == phishing
    assert result.reporter is not None
    assert result.reporter.headers.from_address == "reporter@example.test"
    assert result.reporter.headers.subject == "User-reported suspicious email"
    assert [attachment.filename for attachment in result.retained_attachments] == [
        "evidence.txt"
    ]
    assert result.projected_persisted_bytes == len(phishing) + len(payload)


def test_multiple_attached_roots_are_deterministic_and_visibly_incomplete() -> None:
    first = make_email(subject="First suspicious message")
    second = make_email(subject="Second suspicious message")
    envelope = make_report_envelope(
        [("first.eml", first), ("second.eml", second)],
        subject="Two suspicious messages",
    )

    result = analyze_email(
        envelope,
        limits=_limits(
            max_attachment_bytes=4096,
            max_message_attachment_bytes=8192,
            max_poll_bytes=1024 * 1024 + 8192,
        ),
    )

    assert not result.complete
    assert result.root is not None
    assert result.root.headers.subject == "First suspicious message"
    assert result.root_raw == first
    assert result.reporter is not None
    assert [attachment.filename for attachment in result.retained_attachments] == [
        "second.eml"
    ]
    assert result.warnings[0].code is EmailBudgetLimitType.MULTIPLE_ROOT_CANDIDATES
    assert result.warnings[0].observed == 2


def test_nested_email_traversal_stops_at_configured_depth() -> None:
    nested = make_nested_report(4)

    result = analyze_email(
        nested,
        limits=_limits(max_nested_email_depth=2),
    )

    assert not result.complete
    assert any(
        warning.code is EmailBudgetLimitType.NESTED_EMAIL_DEPTH
        for warning in result.warnings
    )
    assert (
        max(
            warning.observed
            for warning in result.warnings
            if warning.code is EmailBudgetLimitType.NESTED_EMAIL_DEPTH
        )
        == 3
    )


def test_raw_email_limit_returns_metadata_only_partial_result() -> None:
    raw = make_email(subject="Too large to parse", body="x" * 1024)

    result = analyze_email(
        raw,
        limits=_limits(
            max_raw_email_bytes=len(raw) - 1,
            max_poll_bytes=len(raw) - 1 + 32,
        ),
        email_id="provider-id-123",
    )

    assert not result.complete
    assert result.root is None
    assert result.root_raw is None
    assert result.retained_attachments == []
    assert result.projected_persisted_bytes == 0
    assert result.fallback_metadata["email_id"] == "provider-id-123"
    assert result.fallback_metadata["subject"] == "Too large to parse"
    assert result.warnings[0].code is EmailBudgetLimitType.RAW_EMAIL_BYTES
    assert result.warnings[0].observed == len(raw)


def test_container_warning_presentation_preserves_existing_content() -> None:
    warning = EmailAnalysisWarning(
        code=EmailBudgetLimitType.ATTACHMENT_BYTES,
        observed=17,
        limit=16,
        scope="attachment",
        filename="oversized.bin",
        skipped_count=1,
    )
    container = Container(
        name="Reported email",
        description="Original connector description.",
        data={"connector": "metadata"},
        artifacts=[{"name": "Existing artifact", "cef": {"existing": True}}],
    )

    apply_warnings_to_container(container, [warning])

    assert container.description == (
        f"{INCOMPLETE_ANALYSIS_HEADLINE}\n{warning.user_message()}\n\n"
        "Original connector description."
    )
    assert container.data == {
        "connector": "metadata",
        "email_analysis": {
            "complete": False,
            "warnings": [warning.to_dict()],
        },
    }
    assert container.artifacts is not None
    assert container.artifacts[0]["name"] == "Existing artifact"
    artifact = container.artifacts[1]
    assert artifact["name"] == "Email Analysis Warning"
    assert artifact["cef"] == {
        "analysisComplete": False,
        "analysisLimitType": "attachment_bytes",
        "analysisObserved": 17,
        "analysisLimit": 16,
        "analysisScope": "attachment",
        "analysisFilename": "oversized.bin",
        "analysisSkippedCount": 1,
    }


def test_finding_warning_presentation_preserves_identity_and_risk_fields() -> None:
    warning = EmailAnalysisWarning(
        code=EmailBudgetLimitType.ATTACHMENT_COUNT,
        observed=101,
        limit=100,
        scope="message",
        skipped_count=1,
    )
    finding = Finding(
        rule_title="Reported phishing email",
        rule_description="Original finding description.",
        risk_score=73,
        urgency="high",
        additional_fields={"connector": "metadata"},
    )

    apply_warnings_to_finding(finding, [warning])

    assert finding.rule_title == "Reported phishing email"
    assert finding.risk_score == 73
    assert finding.urgency == "high"
    assert finding.rule_description == (
        f"{INCOMPLETE_ANALYSIS_HEADLINE}\n{warning.user_message()}\n\n"
        "Original finding description."
    )
    assert finding.additional_fields == {
        "connector": "metadata",
        "email_analysis": {
            "complete": False,
            "warnings": [warning.to_dict()],
        },
    }


def test_presentation_helpers_are_noops_without_warnings() -> None:
    container = Container(name="No warning", description="Unchanged")
    finding = Finding(rule_title="No warning", rule_description="Unchanged")

    apply_warnings_to_container(container, [])
    apply_warnings_to_finding(finding, [])

    assert container.description == "Unchanged"
    assert container.data is None
    assert container.artifacts is None
    assert finding.rule_description == "Unchanged"
    assert finding.additional_fields is None


def test_string_input_without_attachment_content_counts_only_persisted_raw() -> None:
    raw = make_email(attachments=[AttachmentFixture("metadata-only.bin", b"evidence")])

    result = analyze_email(
        raw.decode("utf-8"),
        limits=_limits(),
        include_attachment_content=False,
    )

    assert result.complete
    assert result.retained_attachments[0].content is None
    assert result.retained_attachments[0].size == len(b"evidence")
    assert result.projected_persisted_bytes == len(raw)


def test_html_body_and_url_are_analyzed() -> None:
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = "sender@example.test"
    message["To"] = "analyst@example.test"
    message["Subject"] = "HTML lure"
    message.set_content("Plain body")
    message.add_alternative(
        '<html><body><a href="https://html.example.test/lure">Open</a></body></html>',
        subtype="html",
    )

    result = analyze_email(message.as_bytes(), limits=_limits())

    assert result.root is not None
    assert "https://html.example.test/lure" in result.root.urls
    assert "<html>" in (result.root.body.html or "")


def test_application_eml_attachment_becomes_root() -> None:
    inner = make_email(subject="Application EML root")
    envelope = make_email(
        subject="Wrapper",
        sender="reporter@example.test",
        attachments=[
            AttachmentFixture("reported.eml", inner, "application", "octet-stream")
        ],
    )

    result = analyze_email(envelope, limits=_limits())

    assert result.root is not None
    assert result.root.headers.subject == "Application EML root"
    assert result.root_raw == inner
    assert result.reporter is not None


def test_invalid_eml_name_remains_an_ordinary_leaf() -> None:
    raw = make_email(attachments=[AttachmentFixture("invalid.eml", b"not an email")])

    result = analyze_email(raw, limits=_limits())

    assert result.reporter is None
    assert result.root is not None
    assert [item.filename for item in result.retained_attachments] == ["invalid.eml"]


def test_oversized_attached_root_returns_reporter_metadata_without_decoding() -> None:
    inner = make_email(subject="Oversized reported root", body="x" * 512)
    envelope = make_report_envelope([("oversized.eml", inner)])
    raw_limit = len(inner) - 1

    result = analyze_email(
        envelope,
        limits=_limits(
            max_raw_email_bytes=raw_limit,
            max_attachment_bytes=16,
            max_message_attachment_bytes=32,
            max_poll_bytes=raw_limit + 32,
        ),
        email_id="outer-provider-id",
    )

    assert result.root is None
    assert result.reporter is not None
    assert result.fallback_metadata == {
        "email_id": "outer-provider-id",
        "filename": "oversized.eml",
        "content_type": "message/rfc822",
    }
    assert result.warnings[-1].code is EmailBudgetLimitType.RAW_EMAIL_BYTES


def test_oversized_additional_root_is_disclosed_as_skipped_leaf() -> None:
    first = make_email(subject="Selected root")
    second = make_email(subject="Oversized extra root", body="x" * 1024)
    envelope = make_report_envelope([("first.eml", first), ("second.eml", second)])
    raw_limit = len(first) + 64

    result = analyze_email(
        envelope,
        limits=_limits(
            max_raw_email_bytes=raw_limit,
            max_attachment_bytes=16,
            max_message_attachment_bytes=32,
            max_poll_bytes=raw_limit + 32,
        ),
    )

    assert result.root is not None
    assert result.root.headers.subject == "Selected root"
    assert result.root.attachments[0].filename == "second.eml"
    assert result.root.attachments[0].skip_reason == "attachment_bytes"
    assert result.root.to_dict()["attachments"][0]["skip_reason"] == "attachment_bytes"
    assert [warning.code for warning in result.warnings] == [
        EmailBudgetLimitType.MULTIPLE_ROOT_CANDIDATES,
        EmailBudgetLimitType.ATTACHMENT_BYTES,
    ]


def test_additional_root_can_fail_exact_decoded_attachment_limit() -> None:
    first = make_email(subject="Selected")
    second = make_email(subject="Extra")
    envelope = make_report_envelope([("first.eml", first), ("second.eml", second)])

    result = analyze_email(
        envelope,
        limits=_limits(
            max_attachment_bytes=len(second) - 1,
            max_message_attachment_bytes=len(second) * 2,
            max_poll_bytes=1024 * 1024 + len(second) * 2,
        ),
    )

    assert result.root is not None
    assert result.root.attachments[0].skip_reason == "attachment_bytes"


def test_direct_msg_is_bounded_and_preserves_attachments(
    msg_with_attachment: bytes,
) -> None:
    result = analyze_email(
        msg_with_attachment,
        limits=_limits(
            max_attachment_bytes=100,
            max_message_attachment_bytes=200,
            max_poll_bytes=1024 * 1024 + 200,
        ),
        email_id="msg-id",
    )

    assert result.complete
    assert result.root is not None
    assert result.root.headers.email_id == "msg-id"
    assert result.root.headers.subject == "MSG With Attachment"
    assert result.retained_attachments[0].filename == "document.pdf"
    assert result.retained_attachments[0].content == b"%PDF-1.4 test content"


def test_direct_html_msg_is_analyzed(msg_html_only: bytes) -> None:
    result = analyze_email(msg_html_only, limits=_limits())

    assert result.root is not None
    assert "https://html.example.com/html-only" in result.root.urls
    assert "<html>" in (result.root.body.html or "")


def test_direct_msg_over_raw_limit_is_metadata_only(msg_plaintext_only: bytes) -> None:
    raw_limit = len(msg_plaintext_only) - 1

    result = analyze_email(
        msg_plaintext_only,
        limits=_limits(
            max_raw_email_bytes=raw_limit,
            max_poll_bytes=raw_limit + 32,
        ),
        email_id="oversized-msg",
    )

    assert result.root is None
    assert result.fallback_metadata == {
        "email_id": "oversized-msg",
        "format": "msg",
    }
    assert result.warnings[0].code is EmailBudgetLimitType.RAW_EMAIL_BYTES


def test_attached_msg_becomes_root(msg_plaintext_only: bytes) -> None:
    envelope = make_email(
        sender="reporter@example.test",
        attachments=[AttachmentFixture("reported.msg", msg_plaintext_only)],
    )

    result = analyze_email(envelope, limits=_limits())

    assert result.root is not None
    assert result.root.headers.subject == "Plaintext Only Subject"
    assert result.root_raw == msg_plaintext_only
    assert result.reporter is not None


def test_nested_msg_content_is_analyzed(msg_plaintext_only: bytes) -> None:
    inner = make_email(
        subject="Selected EML",
        attachments=[AttachmentFixture("nested.msg", msg_plaintext_only)],
    )
    envelope = make_report_envelope([("selected.eml", inner)])

    result = analyze_email(envelope, limits=_limits())

    assert result.root is not None
    assert "Plaintext Only Subject" not in (result.root.body.plain_text or "")
    assert "https://example.com/plain-only" in result.root.urls


def test_warning_presentation_without_original_description() -> None:
    warnings = [
        EmailAnalysisWarning(
            code=EmailBudgetLimitType.ATTACHMENT_COUNT,
            observed=101,
            limit=100,
            scope="message",
            skipped_count=1,
        ),
        EmailAnalysisWarning(
            code=EmailBudgetLimitType.NESTED_EMAIL_DEPTH,
            observed=11,
            limit=10,
            scope="message",
            skipped_count=1,
        ),
    ]
    container = Container(name="No original description")

    apply_warnings_to_container(container, warnings)

    assert container.description is not None
    assert not container.description.endswith("\n\n")
    assert container.artifacts is not None
    assert len(container.artifacts) == 2


def test_internal_payload_guards_cover_nonstandard_message_objects() -> None:
    bytes_part = MagicMock(spec=Message)
    bytes_part.get_payload.return_value = b"abc"
    assert analysis._encoded_payload_size(bytes_part) == 3

    unknown_part = MagicMock(spec=Message)
    unknown_part.get_payload.return_value = object()
    assert analysis._encoded_payload_size(unknown_part) == 0

    plain_part = Message()
    plain_part.set_payload("plain")
    assert analysis._encoded_payload_size(plain_part) == 5

    string_decode = MagicMock(spec=Message)
    string_decode.get_payload.return_value = "decoded"
    assert analysis._decode_part(string_decode) == b"decoded"

    empty_decode = MagicMock(spec=Message)
    empty_decode.get_payload.return_value = None
    assert analysis._decode_part(empty_decode) == b""


def test_candidate_parser_rejects_parse_errors_and_headerless_data() -> None:
    with patch.object(analysis.BytesParser, "parsebytes", side_effect=ValueError):
        assert analysis._parse_rfc_candidate(b"From: sender@example.test") is None

    assert analysis._parse_rfc_candidate(b"not an RFC message") is None


def test_candidate_exact_size_check_catches_underestimated_payload() -> None:
    part = MagicMock(spec=Message)
    part.get_filename.return_value = "understated.eml"
    part.get_content_type.return_value = "application/octet-stream"
    part.get_payload.return_value = "x"
    part.get.return_value = None

    with patch.object(analysis, "_message_bytes", return_value=b"x" * 11):
        candidate = analysis._root_candidate(
            part,
            _limits(
                max_raw_email_bytes=10,
                max_attachment_bytes=5,
                max_message_attachment_bytes=10,
                max_poll_bytes=20,
            ),
        )

    assert candidate is not None
    assert candidate.raw is None
    assert candidate.observed_size == 11


def test_invalid_msg_candidate_is_not_selected() -> None:
    raw = make_email(attachments=[AttachmentFixture("invalid.msg", b"not ole data")])

    result = analyze_email(raw, limits=_limits())

    assert result.reporter is None
    assert result.root is not None
    assert result.retained_attachments[0].filename == "invalid.msg"


def test_mime_depth_guards_raise_before_unbounded_traversal() -> None:
    body = "Content-Type: text/plain; charset=utf-8\r\n\r\nbody\r\n"
    for index in range(51):
        boundary = f"boundary-{index}"
        body = (
            f'Content-Type: multipart/mixed; boundary="{boundary}"\r\n\r\n'
            f"--{boundary}\r\n{body}\r\n--{boundary}--\r\n"
        )
    raw = f"From: sender@example.test\r\nTo: user@example.test\r\n{body}".encode()

    with pytest.raises(ValueError, match="MIME nesting exceeds.*50"):
        analyze_email(raw, limits=_limits())

    parsed = BytesParser(policy=policy.default).parsebytes(raw)
    with pytest.raises(ValueError, match="MIME nesting exceeds.*50"):
        analysis._walk_rfc_message(
            parsed,
            budget=EmailMessageBudget(_limits()),
            accumulator=analysis._AnalysisAccumulator(),
            include_content=True,
        )


def test_internal_multipart_guards_handle_malformed_payloads() -> None:
    malformed = MagicMock(spec=Message)
    malformed.is_multipart.return_value = True
    malformed.get_payload.return_value = "not a child list"
    malformed.get.return_value = None
    malformed.get_filename.return_value = None

    assert analysis._top_level_attachments(malformed) == []

    budget = EmailMessageBudget(_limits())
    accumulator = analysis._AnalysisAccumulator()
    analysis._walk_rfc_message(
        malformed,
        budget=budget,
        accumulator=accumulator,
        include_content=True,
    )
    assert accumulator.attachments == []


def test_fallback_metadata_can_include_selected_filename() -> None:
    headers = analysis.EmailHeaders(email_id="id", subject="subject")

    assert analysis._fallback_from_headers(headers, filename="root.eml") == {
        "email_id": "id",
        "subject": "subject",
        "filename": "root.eml",
    }


def test_reporter_metadata_handles_nonmultipart_and_malformed_multipart() -> None:
    raw = make_email(subject="Simple reporter")
    simple = BytesParser(policy=policy.default).parsebytes(raw)
    reporter = analysis._reporter_data(simple, raw, "provider-id")
    assert reporter.headers.subject == "Simple reporter"

    malformed = MagicMock(spec=Message)
    malformed.is_multipart.return_value = True
    malformed.get_payload.return_value = "not a list"
    malformed.get.side_effect = lambda name: {
        "Subject": "Malformed reporter",
        "From": "reporter@example.test",
    }.get(name)
    malformed.items.return_value = []
    malformed.get_all.return_value = []
    reporter = analysis._reporter_data(malformed, b"malformed", None)
    assert reporter.headers.subject == "Malformed reporter"


def test_empty_and_non_text_body_parts_are_ignored() -> None:
    accumulator = analysis._AnalysisAccumulator()
    empty = Message()
    empty.set_type("text/plain")
    empty.set_payload("")
    binary = Message()
    binary.set_type("application/octet-stream")
    binary.set_payload("data")

    analysis._record_body_part(empty, accumulator)
    analysis._record_body_part(binary, accumulator)

    assert accumulator.body().plain_text is None


def test_msg_helpers_cover_dates_name_fallbacks_and_nested_depth() -> None:
    message = MagicMock()
    message.date = datetime(2026, 8, 31, tzinfo=UTC)
    message.messageId = "msg-id"
    message.to = "to@example.test"
    message.sender = "from@example.test"
    message.subject = "subject"
    message.cc = None
    message.bcc = None
    message.headerDict = {}
    assert analysis._msg_headers(message, "provider-id").date is not None

    metadata_message = MagicMock()
    metadata_message.getStringStream.return_value = None
    assert analysis._msg_attachment_fields(metadata_message, "__attach0") == (
        "unnamed_attachment",
        None,
        None,
    )

    nested = MagicMock()
    nested.body = None
    nested.htmlBody = "<p>nested</p>"
    nested.attachments = []
    embedded = MagicMock()
    embedded.data = nested
    embedded.longFilename = "nested.msg"
    embedded.shortFilename = None
    embedded.name = None
    embedded.mimetype = "application/vnd.ms-outlook"
    parent = MagicMock()
    parent.body = None
    parent.htmlBody = None
    parent.listDir.return_value = [["__attach0"]]
    parent.exists.return_value = False
    parent.initAttachmentFunc.return_value = embedded
    parent.getStringStream.side_effect = ["nested.msg", None, None]
    nested.listDir.return_value = []

    accumulator = analysis._AnalysisAccumulator()
    analysis._walk_msg(
        parent,
        budget=EmailMessageBudget(_limits(max_nested_email_depth=2)),
        accumulator=accumulator,
        include_content=True,
        nested_depth=0,
    )
    assert accumulator.body().html == "<p>nested</p>"

    skipped = analysis._AnalysisAccumulator()
    parent.getStringStream.side_effect = ["nested.msg", None, None]
    analysis._walk_msg(
        parent,
        budget=EmailMessageBudget(_limits(max_nested_email_depth=1)),
        accumulator=skipped,
        include_content=True,
        nested_depth=1,
    )
    assert skipped.attachments[0].skip_reason == "nested_email_depth:2"


def test_msg_stream_preflight_skips_bytes_without_reading_them() -> None:
    message = MagicMock()
    message.getStringStream.side_effect = ["oversized.bin", None, None]
    message._getOleEntry.return_value.size = 17
    budget = EmailMessageBudget(_limits(max_attachment_bytes=16))
    accumulator = analysis._AnalysisAccumulator()

    analysis._record_msg_stream_attachment(
        message,
        "__attach0",
        budget=budget,
        accumulator=accumulator,
        include_content=True,
    )

    message.getStream.assert_not_called()
    assert accumulator.attachments[0].skip_reason == "attachment_bytes"


def test_msg_attachment_directory_discovery_is_ordered_and_deduplicated() -> None:
    message = MagicMock()
    message.listDir.return_value = [
        ["__attach1", "stream"],
        ["not-an-attachment"],
        ["__attach1", "other"],
        ["__attach2"],
        [],
    ]

    assert analysis._msg_attachment_directories(message) == ["__attach1", "__attach2"]
