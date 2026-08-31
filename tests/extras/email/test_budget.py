"""Behavioral contract for bounded email-ingestion accounting."""

from __future__ import annotations

from types import ModuleType

import pytest
from pydantic import ValidationError

import soar_sdk.extras.email.budget as budget_provider
from soar_sdk.asset import BaseAsset, FieldCategory
from soar_sdk.extras.email.budget import (
    MIB,
    EmailAnalysisWarning,
    EmailBudgetAssetMixin,
    EmailBudgetLimits,
    EmailBudgetLimitType,
    EmailMessageBudget,
    EmailPollBudget,
)
from tests.extras.email.contract import assert_budget_provider_contract


def _limits(**overrides: int) -> EmailBudgetLimits:
    values = {
        "max_raw_email_bytes": 100,
        "max_attachment_bytes": 10,
        "max_message_attachment_bytes": 20,
        "max_attachments": 3,
        "max_nested_email_depth": 2,
        "max_poll_bytes": 120,
    }
    values.update(overrides)
    return EmailBudgetLimits(**values)


def test_sdk_satisfies_legacy_compatible_budget_contract() -> None:
    assert_budget_provider_contract(budget_provider)


def test_contract_accepts_an_imported_compatibility_provider() -> None:
    provider = ModuleType("legacy_email_budget")
    for name in (
        "MIB",
        "EmailBudgetLimitType",
        "EmailBudgetLimits",
        "EmailAnalysisWarning",
        "EmailMessageBudget",
        "EmailPollBudget",
    ):
        setattr(provider, name, getattr(budget_provider, name))

    assert_budget_provider_contract(provider)


def test_message_budget_enforces_aggregate_bytes_in_input_order() -> None:
    tracker = EmailMessageBudget(_limits(max_attachment_bytes=20))

    assert tracker.accept_attachment("first.bin", 12)
    assert not tracker.accept_attachment("second.bin", 9)
    assert tracker.attachment_bytes == 12
    assert tracker.attachment_count == 1
    assert tracker.warnings == [
        EmailAnalysisWarning(
            code=EmailBudgetLimitType.MESSAGE_ATTACHMENT_BYTES,
            observed=21,
            limit=20,
            scope="message",
            filename="second.bin",
            skipped_count=1,
        )
    ]
    assert tracker.warnings[0].user_message() == (
        "Threat analysis incomplete: 1 attachment(s) were not analyzed because the "
        "configured per-email decoded attachment limit (0.00 MiB (20 bytes)) was reached."
    )


def test_message_budget_coalesces_subsequent_aggregate_skips() -> None:
    tracker = EmailMessageBudget(_limits(max_attachment_bytes=20))

    assert tracker.accept_attachment("first.bin", 12)
    assert not tracker.accept_attachment("second.bin", 9)
    assert not tracker.accept_attachment("third.bin", 10)

    assert tracker.attachment_bytes == 12
    assert tracker.attachment_count == 1
    assert len(tracker.warnings) == 1
    assert tracker.warnings[0].observed == 31
    assert tracker.warnings[0].skipped_count == 2


def test_message_budget_enforces_count_and_coalesces_skips() -> None:
    tracker = EmailMessageBudget(_limits(max_attachments=2))

    assert tracker.accept_attachment("first.bin", 1)
    assert tracker.accept_attachment("second.bin", 1)
    assert not tracker.accept_attachment("third.bin", 1)
    assert not tracker.accept_attachment("fourth.bin", 1)

    assert tracker.attachment_count == 2
    assert tracker.attachment_bytes == 2
    assert len(tracker.warnings) == 1
    warning = tracker.warnings[0]
    assert warning.code is EmailBudgetLimitType.ATTACHMENT_COUNT
    assert warning.observed == 4
    assert warning.limit == 2
    assert warning.skipped_count == 2
    assert warning.user_message() == (
        "Threat analysis incomplete: 2 attachment(s) were not analyzed because the "
        "configured per-email attachment count (2) was reached."
    )


def test_message_budget_rejects_negative_observations() -> None:
    tracker = EmailMessageBudget(_limits())

    with pytest.raises(ValueError, match="decoded_size"):
        tracker.accept_attachment("impossible.bin", -1)


def test_nested_depth_accepts_boundary_and_rejects_one_level_beyond() -> None:
    tracker = EmailMessageBudget(_limits(max_nested_email_depth=2))

    assert tracker.accept_nested_depth(2)
    assert not tracker.accept_nested_depth(3)
    assert tracker.warnings == [
        EmailAnalysisWarning(
            code=EmailBudgetLimitType.NESTED_EMAIL_DEPTH,
            observed=3,
            limit=2,
            scope="message",
            skipped_count=1,
        )
    ]
    assert tracker.warnings[0].user_message() == (
        "Threat analysis incomplete: nested email content below depth 2 was not analyzed."
    )


def test_warning_messages_cover_raw_email_and_multiple_roots() -> None:
    raw_warning = EmailAnalysisWarning(
        code=EmailBudgetLimitType.RAW_EMAIL_BYTES,
        observed=151 * MIB,
        limit=150 * MIB,
        scope="root",
        skipped_count=1,
    )
    root_warning = EmailAnalysisWarning(
        code=EmailBudgetLimitType.MULTIPLE_ROOT_CANDIDATES,
        observed=2,
        limit=1,
        scope="envelope",
        skipped_count=1,
    )

    assert raw_warning.user_message() == (
        "Threat analysis incomplete: the selected email root was not analyzed because "
        "its raw size (151.00 MiB (158,334,976 bytes)) exceeds the configured raw-email "
        "limit (150.00 MiB (157,286,400 bytes))."
    )
    assert root_warning.user_message() == (
        "Threat analysis incomplete: the reporting envelope contained 2 possible "
        "attached-email roots; only the first valid candidate was used as the analysis root."
    )


def test_poll_budget_only_counts_committed_messages() -> None:
    budget = EmailPollBudget(_limits(max_poll_bytes=120))

    assert budget.can_commit(70)
    budget.commit(70)
    assert budget.committed_bytes == 70

    assert not budget.can_commit(51)
    assert budget.committed_bytes == 70
    assert budget.deferral_message("message-2") == (
        'Email ingestion deferred: processing message "message-2" would exceed the '
        "configured per-poll budget (50 bytes remaining of 120); no records were created "
        "and the checkpoint was not advanced."
    )

    retry_budget = EmailPollBudget(_limits(max_poll_bytes=120))
    assert retry_budget.can_commit(51)
    retry_budget.commit(51)
    assert retry_budget.committed_bytes == 51


def test_poll_budget_accepts_exact_remaining_boundary() -> None:
    budget = EmailPollBudget(_limits(max_poll_bytes=120))

    budget.commit(70)
    assert budget.can_commit(50)
    budget.commit(50)
    assert budget.committed_bytes == 120

    with pytest.raises(ValueError, match="per-poll"):
        budget.commit(1)


class BudgetAsset(EmailBudgetAssetMixin, BaseAsset):
    """Concrete asset used to verify the shared mixin contract."""


def test_asset_mixin_exposes_common_defaults_and_ingest_metadata() -> None:
    asset = BudgetAsset()

    assert asset.email_budget_limits() == EmailBudgetLimits()
    schema = BudgetAsset.to_json_schema()
    expected_defaults = {
        "max_raw_email_size_mb": 150,
        "max_attachment_size_mb": 25,
        "max_email_attachment_total_size_mb": 100,
        "max_email_attachment_count": 100,
        "max_nested_email_depth": 10,
        "max_poll_persisted_size_mb": 250,
    }
    assert {
        name: schema[name]["default"] for name in expected_defaults
    } == expected_defaults
    for name in expected_defaults:
        assert schema[name]["category"] is FieldCategory.INGEST
        assert "MiB" in schema[name]["description"] or name in {
            "max_email_attachment_count",
            "max_nested_email_depth",
        }


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_raw_email_size_mb": 0},
        {"max_attachment_size_mb": -1},
        {"max_email_attachment_total_size_mb": 0},
        {"max_email_attachment_count": 0},
        {"max_nested_email_depth": 0},
        {"max_poll_persisted_size_mb": 0},
        {
            "max_attachment_size_mb": 101,
            "max_email_attachment_total_size_mb": 100,
        },
        {
            "max_raw_email_size_mb": 150,
            "max_email_attachment_total_size_mb": 100,
            "max_poll_persisted_size_mb": 249,
        },
    ],
)
def test_asset_mixin_rejects_invalid_configurations(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        BudgetAsset(**overrides)
