from typing import Any

from pydantic import BaseModel, ConfigDict


class DrilldownSearch(BaseModel):
    """Represents a drilldown search in a finding."""

    name: str
    search: str
    earliest: str
    latest: str


class DrilldownDashboardToken(BaseModel):
    """Represents a token for a drilldown dashboard."""

    name: str
    value: str


class DrilldownDashboard(BaseModel):
    """Represents a drilldown dashboard in a finding."""

    app: str
    dashboard_id: str
    name: str
    tokens: list[DrilldownDashboardToken] | None = None


class FindingAttachment(BaseModel):
    """Represents a file attachment to upload to the SOAR vault during on_es_poll.

    The SDK uploads these to the container vault before creating the finding,
    then populates the finding's email.attachments and email.raw_email_link
    with the resulting vault links.
    """

    file_name: str
    data: bytes
    source_type: str = "Incident"
    is_raw_email: bool = True


class FindingEmail(BaseModel):
    """Email object containing all email-related fields for phishing findings."""

    model_config = ConfigDict(extra="forbid")

    headers: dict[str, Any] | None = None
    body: str | None = None
    urls: list[str] | None = None
    attachments: list[str] | None = None
    raw_email_link: str | None = None


class Finding(BaseModel):
    """Represents a finding to be created during on_es_poll.

    Findings are stored in ES and can be associated with SOAR containers/artifacts
    for investigation workflow.

    Only rule_title is required. All other fields are optional and will use
    ES defaults or asset ingest configuration if not provided.
    """

    model_config = ConfigDict(extra="forbid")

    rule_title: str
    security_domain: str | None = None
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
    risk_event_count: int | None = None
    all_risk_objects: list[str] | None = None
    source: list[str] | None = None
    exclude_map_fields: list[str] | None = None
    queue_id: str | None = None
    email: FindingEmail | None = None
    run_threat_analysis: bool = False
    launch_automation: bool = False
    automation_rule: str | None = None
    finding_source: str | None = None
    attachments: list[FindingAttachment] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the finding to a dictionary for the ES API.

        Excludes the binary attachments field which is only used by the SDK
        for vault upload. The email.attachments and email.raw_email_link
        vault links are included in the serialized output.
        """
        return self.model_dump(exclude_none=True, exclude={"attachments"})
