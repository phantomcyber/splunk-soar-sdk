"""Behavioral contract for safe email-root selection and warning presentation."""

from __future__ import annotations

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
