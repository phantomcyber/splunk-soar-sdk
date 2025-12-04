import pytest
from pydantic import ValidationError

from soar_sdk.models.finding import DrilldownDashboard, DrilldownSearch, Finding


def test_finding_basic():
    """Test basic Finding with required fields."""
    finding = Finding(
        rule_title="Test Finding",
        rule_description="Test Description",
        security_domain="threat",
        risk_object="test@example.com",
        risk_object_type="user",
        risk_score=85.0,
    )

    finding_dict = finding.to_dict()
    assert finding_dict["rule_title"] == "Test Finding"
    assert finding_dict["security_domain"] == "threat"
    assert finding_dict["risk_score"] == 85.0
    assert "status" not in finding_dict


def test_finding_with_complex_fields():
    """Test Finding with drilldowns, annotations, and optional fields."""
    drilldown_search = DrilldownSearch(
        name="search_name", search="index=_internal", earliest="-1d", latest="now"
    )
    drilldown_dashboard = DrilldownDashboard(
        dashboard="dash_id", name="Dashboard", tokens=["token1"]
    )

    finding = Finding(
        rule_title="Risk Threshold Exceeded",
        rule_description="24 hour risk threshold exceeded",
        security_domain="threat",
        risk_object="bad_user@splunk.com",
        risk_object_type="user",
        risk_score=100,
        status="New",
        drilldown_searches=[drilldown_search],
        drilldown_dashboards=[drilldown_dashboard],
        annotations={"mitre_attack": ["T1078", "T1537"]},
        all_risk_objects=["user1@splunk.com", "user2@splunk.com"],
    )

    finding_dict = finding.to_dict()
    assert finding_dict["status"] == "New"
    assert len(finding_dict["drilldown_searches"]) == 1
    assert finding_dict["drilldown_searches"][0]["name"] == "search_name"
    assert len(finding_dict["drilldown_dashboards"]) == 1
    assert finding_dict["annotations"]["mitre_attack"] == ["T1078", "T1537"]
    assert len(finding_dict["all_risk_objects"]) == 2


def test_finding_validation():
    """Test Finding validation for invalid inputs."""
    # Invalid attribute
    with pytest.raises(ValidationError):
        Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score=50.0,
            not_allowed="fail",
        )

    # Missing required fields
    with pytest.raises(ValidationError):
        Finding(rule_title="Test")

    with pytest.raises(ValidationError):
        Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score="invalid",
        )


def test_finding_serialization():
    """Test Finding serialization and deserialization."""
    data = {
        "rule_title": "Test Finding",
        "rule_description": "Test Description",
        "security_domain": "threat",
        "risk_object": "test@example.com",
        "risk_object_type": "user",
        "risk_score": 75.0,
        "status": "New",
    }
    finding = Finding(**data)
    finding_dict = finding.to_dict()
    new_finding = Finding(**finding_dict)
    assert new_finding == finding


def test_drilldown_search():
    """Test DrilldownSearch model."""
    drilldown = DrilldownSearch(
        name="Test", search="index=main", earliest="-24h", latest="now"
    )
    assert drilldown.name == "Test"
    assert drilldown.search == "index=main"

    with pytest.raises(ValidationError):
        DrilldownSearch(name="Test")


def test_drilldown_dashboard():
    """Test DrilldownDashboard model."""
    dashboard = DrilldownDashboard(dashboard="dash_id", name="Dashboard Name")
    assert dashboard.dashboard == "dash_id"
    assert dashboard.tokens is None

    dashboard_with_tokens = DrilldownDashboard(
        dashboard="dash_id", name="Dashboard", tokens=["token1", "token2"]
    )
    assert len(dashboard_with_tokens.tokens) == 2

    with pytest.raises(ValidationError):
        DrilldownDashboard(name="Test")
