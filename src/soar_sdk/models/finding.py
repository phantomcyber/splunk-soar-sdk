from pydantic import BaseModel
from typing import Optional, Any


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
    tokens: Optional[list[str]] = None


class Finding(BaseModel):
    """Represents a finding to be created during on_finding.

    Findings are stored in ES and can be associated with SOAR containers/artifacts
    for investigation workflow.
    """

    class Config:
        """Pydantic config."""

        extra = "forbid"

    rule_title: str
    rule_description: str
    security_domain: str
    risk_object: str
    risk_object_type: str
    risk_score: float
    status: Optional[str] = None
    urgency: Optional[str] = None
    owner: Optional[str] = None
    disposition: Optional[str] = None
    drilldown_searches: Optional[list[DrilldownSearch]] = None
    drilldown_dashboards: Optional[list[DrilldownDashboard]] = None
    annotations: Optional[dict[str, list[str]]] = None
    risk_event_count: Optional[int] = None
    all_risk_objects: Optional[list[str]] = None
    source: Optional[list[str]] = None
    exclude_map_fields: Optional[list[str]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the finding to a dictionary."""
        return self.dict(exclude_none=True)
