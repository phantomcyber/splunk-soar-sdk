"""Canonical limits, accounting, and messages for untrusted email ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Self

from pydantic import model_validator

from soar_sdk.asset import AssetField, FieldCategory

MIB = 1024 * 1024


class EmailBudgetLimitType(str, Enum):
    """Stable reason codes for email-analysis and polling limits."""

    RAW_EMAIL_BYTES = "raw_email_bytes"
    ATTACHMENT_BYTES = "attachment_bytes"
    MESSAGE_ATTACHMENT_BYTES = "message_attachment_bytes"
    ATTACHMENT_COUNT = "attachment_count"
    NESTED_EMAIL_DEPTH = "nested_email_depth"
    MULTIPLE_ROOT_CANDIDATES = "multiple_root_candidates"
    POLL_BYTES = "poll_bytes"


@dataclass(frozen=True)
class EmailBudgetLimits:
    """Validated byte, count, and nesting limits for one ingestion asset."""

    max_raw_email_bytes: int = 150 * MIB
    max_attachment_bytes: int = 25 * MIB
    max_message_attachment_bytes: int = 100 * MIB
    max_attachments: int = 100
    max_nested_email_depth: int = 10
    max_poll_bytes: int = 250 * MIB

    def validate(self) -> None:
        """Raise ``ValueError`` when limits cannot safely bound ingestion."""
        for name in (
            "max_raw_email_bytes",
            "max_attachment_bytes",
            "max_message_attachment_bytes",
            "max_attachments",
            "max_nested_email_depth",
            "max_poll_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")

        if self.max_attachment_bytes > self.max_message_attachment_bytes:
            raise ValueError(
                "max_attachment_bytes must not exceed max_message_attachment_bytes"
            )

        minimum_poll_bytes = (
            self.max_raw_email_bytes + self.max_message_attachment_bytes
        )
        if self.max_poll_bytes < minimum_poll_bytes:
            raise ValueError(
                "max_poll_bytes must be at least max_raw_email_bytes + "
                "max_message_attachment_bytes"
            )


def _format_bytes(value: int) -> str:
    unit = "byte" if value == 1 else "bytes"
    return f"{value / MIB:.2f} MiB ({value:,} {unit})"


@dataclass(frozen=True)
class EmailAnalysisWarning:
    """One machine-readable reason that email analysis was incomplete."""

    code: EmailBudgetLimitType
    observed: int
    limit: int
    scope: str
    filename: str | None = None
    skipped_count: int = 0

    def user_message(self) -> str:
        """Render the canonical analyst-facing warning for this reason."""
        if self.code is EmailBudgetLimitType.RAW_EMAIL_BYTES:
            return (
                "Threat analysis incomplete: the selected email root was not analyzed "
                f"because its raw size ({_format_bytes(self.observed)}) exceeds the "
                f"configured raw-email limit ({_format_bytes(self.limit)})."
            )
        if self.code is EmailBudgetLimitType.ATTACHMENT_BYTES:
            filename = self.filename or "unnamed_attachment"
            return (
                f'Threat analysis incomplete: attachment "{filename}" was not analyzed '
                f"because its decoded size ({_format_bytes(self.observed)}) exceeds the "
                f"configured per-attachment limit ({_format_bytes(self.limit)})."
            )
        if self.code is EmailBudgetLimitType.MESSAGE_ATTACHMENT_BYTES:
            return (
                f"Threat analysis incomplete: {self.skipped_count} attachment(s) were "
                "not analyzed because the configured per-email decoded attachment limit "
                f"({_format_bytes(self.limit)}) was reached."
            )
        if self.code is EmailBudgetLimitType.ATTACHMENT_COUNT:
            return (
                f"Threat analysis incomplete: {self.skipped_count} attachment(s) were "
                "not analyzed because the configured per-email attachment count "
                f"({self.limit}) was reached."
            )
        if self.code is EmailBudgetLimitType.NESTED_EMAIL_DEPTH:
            return (
                "Threat analysis incomplete: nested email content below depth "
                f"{self.limit} was not analyzed."
            )
        if self.code is EmailBudgetLimitType.MULTIPLE_ROOT_CANDIDATES:
            return (
                "Threat analysis incomplete: the reporting envelope contained "
                f"{self.observed} possible attached-email roots; only the first valid "
                "candidate was used as the analysis root."
            )
        raise ValueError(f"{self.code.value} does not have a published warning message")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible warning representation."""
        return {
            "code": self.code.value,
            "observed": self.observed,
            "limit": self.limit,
            "scope": self.scope,
            "filename": self.filename,
            "skipped_count": self.skipped_count,
            "message": self.user_message(),
        }


@dataclass
class EmailMessageBudget:
    """Track accepted and encountered leaf attachments for one analysis root."""

    limits: EmailBudgetLimits
    attachment_bytes: int = 0
    attachment_count: int = 0
    warnings: list[EmailAnalysisWarning] = field(default_factory=list)
    observed_attachment_bytes: int = 0
    observed_attachment_count: int = 0

    def __post_init__(self) -> None:
        self.limits.validate()

    def _coalesce_warning(
        self,
        code: EmailBudgetLimitType,
        *,
        observed: int,
        limit: int,
        scope: str,
        filename: str | None,
    ) -> None:
        for index, warning in enumerate(self.warnings):
            if warning.code is code:
                self.warnings[index] = replace(
                    warning,
                    observed=observed,
                    skipped_count=warning.skipped_count + 1,
                )
                return

        self.warnings.append(
            EmailAnalysisWarning(
                code=code,
                observed=observed,
                limit=limit,
                scope=scope,
                filename=filename,
                skipped_count=1,
            )
        )

    def accept_attachment(self, filename: str, decoded_size: int) -> bool:
        """Accept a decoded leaf if count, individual, and aggregate limits allow it."""
        if decoded_size < 0:
            raise ValueError("decoded_size must not be negative")

        self.observed_attachment_count += 1
        self.observed_attachment_bytes += decoded_size

        if self.attachment_count >= self.limits.max_attachments:
            self._coalesce_warning(
                EmailBudgetLimitType.ATTACHMENT_COUNT,
                observed=self.observed_attachment_count,
                limit=self.limits.max_attachments,
                scope="message",
                filename=filename,
            )
            return False

        if decoded_size > self.limits.max_attachment_bytes:
            self.warnings.append(
                EmailAnalysisWarning(
                    code=EmailBudgetLimitType.ATTACHMENT_BYTES,
                    observed=decoded_size,
                    limit=self.limits.max_attachment_bytes,
                    scope="attachment",
                    filename=filename,
                    skipped_count=1,
                )
            )
            return False

        if (
            self.attachment_bytes + decoded_size
            > self.limits.max_message_attachment_bytes
        ):
            self._coalesce_warning(
                EmailBudgetLimitType.MESSAGE_ATTACHMENT_BYTES,
                observed=self.observed_attachment_bytes,
                limit=self.limits.max_message_attachment_bytes,
                scope="message",
                filename=filename,
            )
            return False

        self.attachment_count += 1
        self.attachment_bytes += decoded_size
        return True

    def accept_nested_depth(self, depth: int) -> bool:
        """Accept nested message content at or above the configured boundary."""
        if depth < 0:
            raise ValueError("depth must not be negative")
        if depth <= self.limits.max_nested_email_depth:
            return True

        self._coalesce_warning(
            EmailBudgetLimitType.NESTED_EMAIL_DEPTH,
            observed=depth,
            limit=self.limits.max_nested_email_depth,
            scope="message",
            filename=None,
        )
        return False


@dataclass
class EmailPollBudget:
    """Count only successfully committed persisted bytes within one poll run."""

    limits: EmailBudgetLimits
    committed_bytes: int = 0

    def __post_init__(self) -> None:
        self.limits.validate()
        if self.committed_bytes < 0:
            raise ValueError("committed_bytes must not be negative")
        if self.committed_bytes > self.limits.max_poll_bytes:
            raise ValueError("committed_bytes exceeds the configured per-poll limit")

    @property
    def remaining_bytes(self) -> int:
        """Return the unused persisted-byte allowance for this invocation."""
        return self.limits.max_poll_bytes - self.committed_bytes

    def can_commit(self, projected_bytes: int) -> bool:
        """Return whether a fully staged message fits without consuming budget."""
        if projected_bytes < 0:
            raise ValueError("projected_bytes must not be negative")
        return projected_bytes <= self.remaining_bytes

    def commit(self, projected_bytes: int) -> None:
        """Consume budget after persistence succeeds."""
        if not self.can_commit(projected_bytes):
            raise ValueError("message exceeds the configured per-poll budget")
        self.committed_bytes += projected_bytes

    def deferral_message(self, message_id: str) -> str:
        """Render the operational-only message for a staged email that did not fit."""
        return (
            f'Email ingestion deferred: processing message "{message_id}" would exceed '
            "the configured per-poll budget "
            f"({self.remaining_bytes} bytes remaining of {self.limits.max_poll_bytes}); "
            "no records were created and the checkpoint was not advanced."
        )


class EmailBudgetAssetMixin:
    """Shared optional asset fields for bounded email-ingestion connectors."""

    max_raw_email_size_mb: int = AssetField(
        description=(
            "Maximum raw size of the selected analysis root in MiB. A larger root "
            "creates a metadata-only result marked as incomplete."
        ),
        default=150,
        category=FieldCategory.INGEST,
    )
    max_attachment_size_mb: int = AssetField(
        description=(
            "Maximum decoded size of one leaf attachment in MiB. A larger attachment "
            "is omitted and the result is marked as incomplete."
        ),
        default=25,
        category=FieldCategory.INGEST,
    )
    max_email_attachment_total_size_mb: int = AssetField(
        description=(
            "Maximum total decoded size of retained leaf attachments per analysis root "
            "in MiB. Remaining attachments are omitted and the result is marked as "
            "incomplete."
        ),
        default=100,
        category=FieldCategory.INGEST,
    )
    max_email_attachment_count: int = AssetField(
        description=(
            "Maximum number of retained leaf attachments per analysis root. Remaining "
            "attachments are omitted and the result is marked as incomplete."
        ),
        default=100,
        category=FieldCategory.INGEST,
    )
    max_nested_email_depth: int = AssetField(
        description=(
            "Maximum attached-email nesting depth analyzed per root. Deeper content is "
            "omitted and the result is marked as incomplete."
        ),
        default=10,
        category=FieldCategory.INGEST,
    )
    max_poll_persisted_size_mb: int = AssetField(
        description=(
            "Maximum projected raw and decoded content persisted per poll in MiB. An "
            "email that would exceed the remaining budget is deferred without creating "
            "records or advancing its checkpoint."
        ),
        default=250,
        category=FieldCategory.INGEST,
    )

    def email_budget_limits(self) -> EmailBudgetLimits:
        """Convert configured binary-MiB values into validated byte limits."""
        limits = EmailBudgetLimits(
            max_raw_email_bytes=self.max_raw_email_size_mb * MIB,
            max_attachment_bytes=self.max_attachment_size_mb * MIB,
            max_message_attachment_bytes=(
                self.max_email_attachment_total_size_mb * MIB
            ),
            max_attachments=self.max_email_attachment_count,
            max_nested_email_depth=self.max_nested_email_depth,
            max_poll_bytes=self.max_poll_persisted_size_mb * MIB,
        )
        limits.validate()
        return limits

    @model_validator(mode="after")
    def _validate_email_budget_configuration(self) -> Self:
        self.email_budget_limits()
        return self


def warning_data(warnings: list[EmailAnalysisWarning]) -> dict[str, Any]:
    """Build the common structured representation used by containers and findings."""
    return {
        "complete": not warnings,
        "warnings": [warning.to_dict() for warning in warnings],
    }
