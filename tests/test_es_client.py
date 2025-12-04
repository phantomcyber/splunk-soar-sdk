import respx
from httpx import Response

from soar_sdk.es_client import ESClient
from soar_sdk.models.finding import Finding


@respx.mock
def test_es_client_creates_finding_with_expected_payload():
    """Ensure ESClient posts the correct payload and parses the response."""
    base_url = "https://es.example"
    session_key = "session-key"
    finding = Finding(
        rule_title="Suspicious Authentication",
        rule_description="Multiple failed logins detected",
        security_domain="threat",
        risk_object="user@example.com",
        risk_object_type="user",
        risk_score=42.0,
        status="new",
        urgency="high",
    )
    expected_payload = finding.model_dump()

    route = respx.post(f"{base_url}/services/public/v2/findings").mock(
        return_value=Response(
            status_code=201,
            json={
                **expected_payload,
                "finding_id": "finding-123",
                "_time": "2024-01-01T00:00:00Z",
            },
        )
    )

    client = ESClient(base_url=base_url, session_key=session_key)
    response = client.findings.create(finding)

    assert route.called
    request = route.calls[0].request

    assert request.headers["Authorization"] == f"Splunk {session_key}"
    assert response.finding_id == "finding-123"
    assert response.rule_title == finding.rule_title
    assert response.risk_score == finding.risk_score
    assert response.time == "2024-01-01T00:00:00Z"
