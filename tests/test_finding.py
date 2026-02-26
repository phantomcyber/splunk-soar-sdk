from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from soar_sdk.models.finding import (
    DrilldownDashboard,
    DrilldownDashboardToken,
    DrilldownSearch,
    Finding,
    FindingAttachment,
)


def test_finding_with_complex_fields():
    """Test Finding with drilldowns, annotations, and optional fields."""
    drilldown_search = DrilldownSearch(
        name="search_name", search="index=_internal", earliest="-1d", latest="now"
    )
    drilldown_dashboard = DrilldownDashboard(
        app="DA-ESS-NetworkProtection",
        dashboard_id="email_activity",
        name="Dashboard",
        tokens=[DrilldownDashboardToken(name="form.token_name", value="token_value")],
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

    with pytest.raises(ValidationError):
        Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score="invalid",
        )


def test_finding_minimal():
    """Test Finding with only required field (rule_title)."""
    finding = Finding(rule_title="Minimal Finding")
    assert finding.rule_title == "Minimal Finding"
    assert finding.security_domain is None


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
    dashboard = DrilldownDashboard(
        app="DA-ESS-NetworkProtection",
        dashboard_id="email_activity",
        name="Dashboard Name",
    )
    assert dashboard.app == "DA-ESS-NetworkProtection"
    assert dashboard.dashboard_id == "email_activity"
    assert dashboard.tokens is None

    dashboard_with_tokens = DrilldownDashboard(
        app="DA-ESS-NetworkProtection",
        dashboard_id="email_activity",
        name="Dashboard",
        tokens=[
            DrilldownDashboardToken(name="form.token_name", value="token_value"),
            DrilldownDashboardToken(name="form.name", value="another_value"),
        ],
    )
    assert len(dashboard_with_tokens.tokens) == 2
    assert dashboard_with_tokens.tokens[0].name == "form.token_name"
    assert dashboard_with_tokens.tokens[0].value == "token_value"

    with pytest.raises(ValidationError):
        DrilldownDashboard(name="Test")


def test_finding_attachment():
    """Test FindingAttachment model."""
    attachment = FindingAttachment(file_name="email.eml", data=b"raw email content")
    assert attachment.file_name == "email.eml"
    assert attachment.data == b"raw email content"


def test_finding_with_attachments():
    """Test Finding with attachments - attachments excluded from to_dict."""
    attachment = FindingAttachment(file_name="email.eml", data=b"content")
    finding = Finding(
        rule_title="Phishing Email",
        attachments=[attachment],
    )
    assert finding.attachments is not None
    assert len(finding.attachments) == 1
    finding_dict = finding.to_dict()
    assert "attachments" not in finding_dict


def test_soar_client_create_finding(app_with_action):
    """Test SOARClient.create_finding calls post and returns response."""
    from soar_sdk.app import App

    app: App = app_with_action
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "finding_id": "test-id",
        "_time": "2025-01-01T00:00:00Z",
    }
    app.soar_client.post = MagicMock(return_value=mock_response)

    result = app.soar_client.create_finding({"rule_title": "Test"})

    app.soar_client.post.assert_called_once_with(
        "/rest/enterprise_security/findings", json={"rule_title": "Test"}, timeout=30.0
    )
    assert result["finding_id"] == "test-id"


def test_soar_client_create_findings_bulk(app_with_action):
    """Test SOARClient.create_findings_bulk calls bulk endpoint."""
    from soar_sdk.app import App

    app: App = app_with_action
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "success",
        "created": 2,
        "failed": 0,
        "findings": ["id-1", "id-2"],
        "errors": [],
    }
    app.soar_client.post = MagicMock(return_value=mock_response)

    findings = [{"rule_title": "Finding 1"}, {"rule_title": "Finding 2"}]
    result = app.soar_client.create_findings_bulk(findings)

    app.soar_client.post.assert_called_once_with(
        "/rest/enterprise_security/findings/bulk_create",
        json=findings,
        timeout=30.0,
    )
    assert result["created"] == 2
    assert result["findings"] == ["id-1", "id-2"]


def test_soar_client_create_findings_bulk_with_container_ids(app_with_action):
    """Test SOARClient.create_findings_bulk wraps payload when container_ids provided."""
    from soar_sdk.app import App

    app: App = app_with_action
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "success",
        "created": 1,
        "failed": 0,
        "findings": ["id-1"],
        "container_ids": [42],
        "errors": [],
    }
    app.soar_client.post = MagicMock(return_value=mock_response)

    findings = [{"rule_title": "Finding 1"}]
    result = app.soar_client.create_findings_bulk(findings, container_ids=[42])

    call_args = app.soar_client.post.call_args
    assert call_args[1]["json"] == {"findings": findings, "container_ids": [42]}
    assert result["container_ids"] == [42]


def test_soar_client_create_findings_bulk_empty(app_with_action):
    """Test SOARClient.create_findings_bulk with empty list returns immediately."""
    from soar_sdk.app import App

    app: App = app_with_action
    app.soar_client.post = MagicMock()

    result = app.soar_client.create_findings_bulk([])

    app.soar_client.post.assert_not_called()
    assert result["created"] == 0


def test_soar_client_create_findings_bulk_exceeds_limit(app_with_action):
    """Test SOARClient.create_findings_bulk rejects more than 500 findings."""
    from soar_sdk.app import App

    app: App = app_with_action
    findings = [{"rule_title": f"Finding {i}"} for i in range(501)]

    with pytest.raises(ValueError, match="Maximum 500"):
        app.soar_client.create_findings_bulk(findings)


def test_soar_client_upload_finding_attachment(app_with_action):
    """Test SOARClient.upload_finding_attachment calls post with encoded data."""
    import base64

    from soar_sdk.app import App

    app: App = app_with_action
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "attachment-1"}
    app.soar_client.post = MagicMock(return_value=mock_response)

    result = app.soar_client.upload_finding_attachment(
        "finding-123", "test.eml", b"raw data"
    )

    app.soar_client.post.assert_called_once()
    call_args = app.soar_client.post.call_args
    assert call_args[0][0] == "/rest/enterprise_security/findings/finding-123/files"
    assert call_args[1]["json"]["file_name"] == "test.eml"
    assert call_args[1]["json"]["data"] == base64.b64encode(b"raw data").decode("utf-8")
    assert call_args[1]["json"]["source_type"] == "Incident"
    assert call_args[1]["json"]["is_raw_email"] is True
    assert result == {"id": "attachment-1"}
