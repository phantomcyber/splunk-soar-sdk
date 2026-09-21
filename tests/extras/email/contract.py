"""Reusable behavioral assertions for SDK and legacy email-budget providers."""

from __future__ import annotations

from types import ModuleType

import pytest


def assert_budget_provider_contract(provider: ModuleType) -> None:
    """Assert behavior that compatibility copies must share with the SDK."""
    mib = provider.MIB
    limits = provider.EmailBudgetLimits()

    assert mib == 1024 * 1024
    assert limits.max_raw_email_bytes == 150 * mib
    assert limits.max_attachment_bytes == 25 * mib
    assert limits.max_message_attachment_bytes == 100 * mib
    assert limits.max_attachments == 100
    assert limits.max_nested_email_depth == 10
    assert limits.max_poll_bytes == 250 * mib
    limits.validate()

    tracker = provider.EmailMessageBudget(limits)
    assert tracker.accept_attachment("at-limit.bin", 25 * mib)
    assert tracker.attachment_count == 1
    assert tracker.attachment_bytes == 25 * mib

    tracker = provider.EmailMessageBudget(limits)
    assert not tracker.accept_attachment("over-limit.bin", 25 * mib + 1)
    assert tracker.attachment_count == 0
    assert tracker.attachment_bytes == 0
    assert len(tracker.warnings) == 1

    warning = tracker.warnings[0]
    assert warning.code is provider.EmailBudgetLimitType.ATTACHMENT_BYTES
    assert warning.user_message() == (
        'Threat analysis incomplete: attachment "over-limit.bin" was not analyzed '
        "because its decoded size (25.00 MiB (26,214,401 bytes)) exceeds the "
        "configured per-attachment limit (25.00 MiB (26,214,400 bytes))."
    )
    assert warning.to_dict() == {
        "code": "attachment_bytes",
        "observed": 25 * mib + 1,
        "limit": 25 * mib,
        "scope": "attachment",
        "filename": "over-limit.bin",
        "skipped_count": 1,
        "message": warning.user_message(),
    }

    invalid_limits = (
        (provider.EmailBudgetLimits(max_raw_email_bytes=0), "positive"),
        (provider.EmailBudgetLimits(max_attachment_bytes=-1), "positive"),
        (provider.EmailBudgetLimits(max_message_attachment_bytes=0), "positive"),
        (provider.EmailBudgetLimits(max_attachments=0), "positive"),
        (provider.EmailBudgetLimits(max_nested_email_depth=0), "positive"),
        (provider.EmailBudgetLimits(max_poll_bytes=0), "positive"),
        (
            provider.EmailBudgetLimits(
                max_attachment_bytes=2 * mib,
                max_message_attachment_bytes=mib,
            ),
            "max_attachment_bytes.*max_message_attachment_bytes",
        ),
        (
            provider.EmailBudgetLimits(
                max_raw_email_bytes=150 * mib,
                max_message_attachment_bytes=100 * mib,
                max_poll_bytes=249 * mib,
            ),
            "max_poll_bytes.*max_raw_email_bytes.*max_message_attachment_bytes",
        ),
    )
    for invalid, message_pattern in invalid_limits:
        with pytest.raises(ValueError, match=message_pattern):
            invalid.validate()
