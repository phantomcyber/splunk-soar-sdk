from typing import Any

from pydantic import BaseModel, ConfigDict


class DrilldownSearch(BaseModel):
    """Represents a drilldown search in a finding."""

    name: str
    search: str
    earliest: str
    latest: str


class DrilldownDashboard(BaseModel):
    """Represents a drilldown dashboard in a finding."""

    dashboard: str
    name: str
    tokens: list[str] | None = None


class Finding(BaseModel):
    """Represents a finding to be created during on_es_poll.

    Findings are stored in ES and can be associated with SOAR containers/artifacts
    for investigation workflow.

    Only rule_title and security_domain are required. All other fields are optional
    and will use ES defaults if not provided.
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields
    rule_title: str
    security_domain: str

    # Optional fields
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

    def to_dict(self) -> dict[str, Any]:
        """Convert the finding to a dictionary."""
        return self.model_dump(exclude_none=True)
