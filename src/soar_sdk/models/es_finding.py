"""Models for the ES public findings API, independent of classic SOAR polling."""

__lazy_modules__ = {"pydantic", "typing"}

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _RequestModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, allow_inf_nan=False, revalidate_instances="always"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize ES field names, omitting optional fields set to None."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class DrilldownSearch(_RequestModel):
    """An ES drilldown search; all four string fields are required."""

    name: str
    search: str
    earliest: str
    latest: str


class DrilldownDashboard(_RequestModel):
    """An ES dashboard with required name/dashboard and optional string tokens."""

    name: str
    dashboard: str
    tokens: list[str] | None = None


class EmailAttachment(_RequestModel):
    """Email attachment metadata, not an AR-2060 upload target or attachment ID."""

    filename: str
    filesize: int | None = Field(default=None, ge=0, le=2147483647)
    url: str | None = None


class EmailReporter(_RequestModel):
    """Reporter metadata; only the ES field ``from`` is required."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: list[str] | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    subject: str | None = None
    message_id: str | None = None
    id: str | None = None
    body: str | None = None
    date: str | None = None


class PhishingEmail(_RequestModel):
    """The optional ES phishing email object; headers are free-form metadata."""

    headers: dict[str, Any] | None = None
    body: str | None = None
    urls: list[str] | None = None
    attachments: list[EmailAttachment] | None = None
    raw_email_link: str | None = None
    reporter: EmailReporter | None = None


class AdditionalField(_RequestModel):
    """An ES additional_fields entry; the schema makes both strings optional."""

    name: str | None = None
    value: str | None = None


class CreateFindingRequest(_RequestModel):
    """CreateManualFindingRequest from the ES public OpenAPI specification.

    ``rule_title`` and ``security_domain`` are required. All other fields are
    optional; omitted values leave defaults to ES. ``None`` means omit, not
    JSON null. Unlike classic ``Finding``, this model contains only ES wire
    fields and does not upload files or apply asset ingest defaults.
    """

    rule_title: str
    security_domain: str
    rule_description: str | None = None
    risk_object: str | None = None
    risk_object_type: str | None = None
    risk_score: float | None = None
    status: str | None = None
    urgency: str | None = None
    owner: str | None = None
    disposition: str | None = None
    drilldown_searches: list[DrilldownSearch] | None = None
    drilldown_dashboards: list[DrilldownDashboard] | None = None
    annotations: dict[str, list[str]] | None = None
    risk_event_count: float | None = None
    all_risk_objects: list[str] | None = None
    source: list[str] | None = None
    exclude_map_fields: list[str] | None = None
    queue_id: str | None = None
    email: PhishingEmail | None = None
    run_threat_analysis: bool | None = None
    launch_automation: bool | None = None
    automation_rule: str | None = None
    finding_source: str | None = None
    investigation_type: str | None = None
    additional_fields: list[AdditionalField] | None = None


class CreateFindingResponse(BaseModel):
    """CreateManualFindingResponse; unknown ES response fields are ignored.

    ``created_time`` serializes as ``_time``. The opaque ``finding_id`` can be
    passed unchanged as AR-2060's ``subject_id``.
    """

    model_config = ConfigDict(strict=True)

    created_time: str = Field(alias="_time")
    finding_id: str
    risk_object: str | None = None
    risk_object_type: Literal["system", "user", "other"] | None = None
    risk_score: str | None = None
    creator: str | None = None
    status: str | None = None
    urgency: str | None = None
    disposition: str | None = None
    owner_realname: str | None = None
    info_max_time: str | None = None
    drilldown_searches: list[dict[str, Any]] | None = None
    drilldown_dashboards: list[dict[str, Any]] | None = None
    queue_id: str | None = None
    finding_source: str | None = None
    investigation_type: str | None = None
    run_threat_analysis: bool | None = None
    launch_automation: bool | None = None
    automation_rule: str | None = None
    email: dict[str, Any] | None = None


class FindingCreateResult(BaseModel):
    """One direct create_findings_bulk outcome, in input order; index is zero-based.

    Successful results have a finding_id. Failures have a safe error_code,
    message, and an HTTP status_code when ES returned one. No request, response
    body, credentials, or original transport exception is retained.
    """

    index: int
    finding_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    status_code: int | None = None

    @property
    def success(self) -> bool:
        """Whether ES returned a validated created finding ID."""
        return self.finding_id is not None
