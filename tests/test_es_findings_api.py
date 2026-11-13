import json
import traceback
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft4Validator, FormatChecker
from pydantic import SecretStr, ValidationError

from soar_sdk.apis._es_findings import _create_es_finding
from soar_sdk.exceptions import (
    ActionFailure,
    FindingAPIError,
    FindingAuthorizationError,
    FindingConfigurationError,
    FindingRateLimitError,
    FindingTimeoutError,
    FindingUnavailableError,
    FindingValidationError,
)
from soar_sdk.models import (
    CreateFindingRequest,
    CreateFindingResponse,
    FindingCreateResult,
)
from soar_sdk.models.es_finding import (
    AdditionalField,
    DrilldownDashboard,
    DrilldownSearch,
    EmailAttachment,
    EmailReporter,
    PhishingEmail,
)

BASE_URL = "https://es.example:8089/servicesNS/nobody/missioncontrol"
ENDPOINT = BASE_URL + "/public/v2/findings"
TOKEN = "execution-only-secret"
CREATED = {"_time": "2026-11-11T12:00:00+00:00", "finding_id": "opaque@@notable@@id"}
MINIMAL = {"rule_title": "Reported phishing", "security_domain": "threat"}


@pytest.fixture
def es_schema():
    return json.loads(
        (Path(__file__).parent / "fixtures/es_findings_openapi.json").read_text()
    )


def validator(es_schema, name):
    return Draft4Validator(
        {**es_schema, "$ref": f"#/components/schemas/{name}"},
        format_checker=FormatChecker(),
    )


def test_minimal_payload_matches_openapi_without_inventing_defaults(es_schema):
    finding = CreateFindingRequest(**MINIMAL)
    assert finding.to_dict() == MINIMAL
    validator(es_schema, "CreateManualFindingRequest").validate(finding.to_dict())
    for required in ("rule_title", "security_domain"):
        with pytest.raises(ValidationError):
            CreateFindingRequest.model_validate(
                {key: value for key, value in MINIMAL.items() if key != required}
            )


def test_complete_payload_matches_openapi(es_schema):
    finding = CreateFindingRequest(
        **MINIMAL,
        rule_description="Review this message",
        risk_object="user@example.com",
        risk_object_type="user",
        risk_score=80,
        status="New",
        urgency="high",
        owner="analyst",
        disposition="disposition:6",
        drilldown_searches=[
            DrilldownSearch(
                name="Events", search="index=mail", earliest="-1d", latest="now"
            )
        ],
        drilldown_dashboards=[
            DrilldownDashboard(
                name="Mail", dashboard="mail_dashboard", tokens=["token1"]
            )
        ],
        annotations={"mitre_attack": ["T1566"]},
        risk_event_count=1.5,
        all_risk_objects=["user@example.com"],
        source=["mail"],
        exclude_map_fields=["user"],
        queue_id="phishing",
        email=PhishingEmail(
            headers={"from": "attacker@example.com", "received": ["mail.example"]},
            body="Suspicious email",
            urls=["https://example.com"],
            attachments=[
                EmailAttachment(
                    filename="evidence.pdf",
                    filesize=20,
                    url="https://files.example/evidence",
                )
            ],
            raw_email_link="https://files.example/raw-email",
            reporter=EmailReporter(
                from_="reporter@example.com",
                to=["security@example.com"],
                cc=[],
                bcc=[],
                subject="Please review",
                message_id="<id@example.com>",
                id="mail-id",
                body="Report",
                date="2026-11-11",
            ),
        ),
        run_threat_analysis=True,
        launch_automation=True,
        automation_rule="phishing",
        finding_source="mail-connector",
        investigation_type="default",
        additional_fields=[
            AdditionalField(name="src", value="192.0.2.1"),
            AdditionalField(),
        ],
    )
    payload = finding.to_dict()
    validator(es_schema, "CreateManualFindingRequest").validate(payload)
    assert payload["email"]["reporter"]["from"] == "reporter@example.com"
    assert payload["drilldown_dashboards"] == [
        {"name": "Mail", "dashboard": "mail_dashboard", "tokens": ["token1"]}
    ]
    assert payload["additional_fields"] == [{"name": "src", "value": "192.0.2.1"}, {}]
    assert set(payload) == set(
        es_schema["components"]["schemas"]["CreateManualFindingRequest"]["properties"]
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"rule_title": None},
        {"security_domain": None},
        {"risk_score": True},
        {"risk_score": float("nan")},
        {"risk_event_count": "2"},
        {"email": {"headers": {"unserializable": object()}}},
        {"rule_title": "\ud800"},
        {"additional_fields": {"src": 123}},
        {"attachment_ids": ["id"]},
        {"drilldown_searches": [{"name": "Incomplete"}]},
        {
            "drilldown_dashboards": [
                {"name": "Classic", "app": "search", "dashboard_id": "id"}
            ]
        },
        {
            "drilldown_dashboards": [
                {
                    "name": "Mail",
                    "dashboard": "mail",
                    "tokens": [{"name": "x", "value": "y"}],
                }
            ]
        },
        {"email": {"attachments": [{"filename": "x", "filesize": -1}]}},
        {"email": {"attachments": [{"filename": "x", "filesize": 2147483648}]}},
        {"email": {"reporter": {"from": "user@example.com", "to": 123}}},
    ],
)
def test_invalid_payload_is_rejected_without_http(respx_mock, patch):
    with pytest.raises(FindingValidationError) as caught:
        _create_es_finding({**MINIMAL, **patch}, base_url=BASE_URL, token=TOKEN)
    assert isinstance(caught.value, ActionFailure)
    assert caught.value.status_code is None
    assert not respx_mock.calls


def test_mutated_model_is_revalidated(respx_mock):
    finding = CreateFindingRequest(**MINIMAL)
    finding.security_domain = None
    with pytest.raises(FindingValidationError):
        _create_es_finding(finding, base_url=BASE_URL, token=TOKEN)
    assert not respx_mock.calls


def test_unencodable_item_does_not_abort_the_batch(
    app_with_action, monkeypatch, respx_mock
):
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (BASE_URL, TOKEN))
    route = respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    response = api.create_findings_bulk([{**MINIMAL, "rule_title": "\ud800"}, MINIMAL])
    assert response["status"] == "partial"
    assert response["results"][0]["error_code"] == "validation"
    assert response["results"][1]["finding_id"] == CREATED["finding_id"]
    assert route.call_count == 1


@pytest.mark.parametrize("operation", ["create_finding", "create_findings_bulk"])
def test_existing_api_adapts_legacy_payload_without_mutation(
    app_with_action, monkeypatch, respx_mock, es_schema, operation
):
    from soar_sdk.models.finding import Finding, FindingEmail, FindingEmailReporter

    finding = Finding(
        **MINIMAL,
        email=FindingEmail(
            reporter=FindingEmailReporter(
                from_="reporter@example.com",
                to="security@example.com",
                cc="manager@example.com",
                bcc="audit@example.com",
            )
        ),
        additional_fields={"src": "192.0.2.1"},
    )
    payload = finding.to_dict()
    original = json.loads(json.dumps(payload))
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (BASE_URL, TOKEN))
    route = respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    result = getattr(api, operation)(
        payload if operation == "create_finding" else [payload]
    )
    finding_ids = (
        [result["finding_id"]] if operation == "create_finding" else result["findings"]
    )
    assert finding_ids == [CREATED["finding_id"]]
    sent = json.loads(route.calls[0].request.content)
    validator(es_schema, "CreateManualFindingRequest").validate(sent)
    for field in ("to", "cc", "bcc"):
        assert sent["email"]["reporter"][field] == [
            original["email"]["reporter"][field]
        ]
    assert sent["additional_fields"] == [{"name": "src", "value": "192.0.2.1"}]
    assert payload == original
    assert finding.to_dict() == original


def test_empty_legacy_additional_fields_and_email_remain_valid(respx_mock):
    route = respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    _create_es_finding(
        {**MINIMAL, "email": {}, "additional_fields": {}},
        base_url=BASE_URL,
        token=TOKEN,
    )
    assert json.loads(route.calls[0].request.content) == {
        **MINIMAL,
        "email": {},
        "additional_fields": [],
    }


def test_openapi_model_stays_strict_for_legacy_shapes():
    with pytest.raises(ValidationError):
        CreateFindingRequest(
            **MINIMAL,
            email={
                "reporter": {"from": "user@example.com", "to": "security@example.com"}
            },
        )
    with pytest.raises(ValidationError):
        CreateFindingRequest(**MINIMAL, additional_fields={"src": "host"})


@pytest.mark.parametrize("operation", ["create_finding", "create_findings_bulk"])
def test_classic_proxy_receives_original_legacy_payload(
    app_with_action, mocker, operation
):
    payload = {
        "rule_title": "Legacy",
        "email": {
            "reporter": {"from": "user@example.com", "to": "security@example.com"}
        },
        "additional_fields": {"src": "host"},
    }
    original = json.loads(json.dumps(payload))
    post = mocker.patch.object(app_with_action.soar_client, "post")
    response = post.return_value.json.return_value
    assert (
        getattr(app_with_action.soar_client, operation)(
            payload if operation == "create_finding" else [payload]
        )
        is response
    )
    assert post.call_args.kwargs["json"] == (
        original if operation == "create_finding" else [original]
    )
    assert payload == original


@pytest.mark.parametrize(
    "base_url",
    [BASE_URL, BASE_URL + "/", "https://es.example:8089", "https://es.example:8089/"],
)
@pytest.mark.parametrize("secret", [TOKEN, SecretStr(TOKEN)])
def test_create_uses_existing_api_and_separate_auth(
    app_with_action, respx_mock, monkeypatch, base_url, secret
):
    route = respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (base_url, secret))
    assert api.create_finding(CreateFindingRequest(**MINIMAL).to_dict()) == CREATED
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "Cookie" not in request.headers
    assert "ph-auth-token" not in request.headers
    assert json.loads(request.content) == MINIMAL
    assert request.extensions["timeout"]["read"] == 30.0
    assert TOKEN not in repr(vars(api))


def test_explicit_timeout_and_false_values_are_preserved(respx_mock):
    route = respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    _create_es_finding(
        {**MINIMAL, "launch_automation": False, "run_threat_analysis": False},
        base_url=BASE_URL,
        token=TOKEN,
        timeout=2.5,
    )
    request = route.calls[0].request
    assert request.extensions["timeout"]["read"] == 2.5
    assert json.loads(request.content)["run_threat_analysis"] is False
    assert json.loads(request.content)["launch_automation"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"base_url": "es.example"},
        {"base_url": "ftp://es.example"},
        {"base_url": "https://user:password@es.example"},
        {"base_url": "https://es.example?token=secret"},
        {"base_url": "https://es.example/#fragment"},
        {"base_url": "https://[invalid"},
        {"base_url": None},
        {"base_url": f"https://es.example/{TOKEN}"},
        {"token": ""},
        {"token": None},
        {"token": "token\n"},
        {"token": "non-ascii-é"},
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": None},
        {"timeout": float("inf")},
    ],
)
def test_invalid_connection_configuration_does_not_send_request(respx_mock, changes):
    with pytest.raises(FindingConfigurationError):
        _create_es_finding(MINIMAL, **{"base_url": BASE_URL, "token": TOKEN, **changes})
    assert not respx_mock.calls


@pytest.mark.parametrize(
    "status, exception, code",
    [
        (400, FindingValidationError, "validation"),
        (401, FindingAuthorizationError, "authorization"),
        (403, FindingAuthorizationError, "authorization"),
        (404, FindingValidationError, "validation"),
        (409, FindingValidationError, "validation"),
        (422, FindingValidationError, "validation"),
        (429, FindingRateLimitError, "rate_limit"),
        (500, FindingUnavailableError, "unavailable"),
        (502, FindingUnavailableError, "unavailable"),
        (503, FindingUnavailableError, "unavailable"),
        (200, FindingAPIError, "response"),
        (202, FindingAPIError, "response"),
        (302, FindingAPIError, "response"),
        (307, FindingAPIError, "response"),
    ],
)
def test_status_mapping_does_not_retry_redirect_or_expose_response(
    respx_mock, caplog, status, exception, code
):
    caplog.set_level("DEBUG")
    route = respx_mock.post(ENDPOINT).respond(
        status,
        text=f"upstream echoed {TOKEN}",
        headers={"Location": "https://elsewhere.example"},
    )
    with pytest.raises(exception) as caught:
        _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)
    assert caught.value.error_code == code
    assert caught.value.status_code == status
    assert route.call_count == 1
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "error_type, exception",
    [
        (httpx.ReadTimeout, FindingTimeoutError),
        (httpx.ConnectTimeout, FindingTimeoutError),
        (httpx.ConnectError, FindingUnavailableError),
        (httpx.RemoteProtocolError, FindingUnavailableError),
    ],
)
def test_transport_exceptions_are_not_retained(
    respx_mock, caplog, error_type, exception
):
    caplog.set_level("DEBUG")
    route = respx_mock.post(ENDPOINT).mock(
        side_effect=error_type(f"transport echoed {TOKEN}")
    )
    with pytest.raises(exception) as caught:
        _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)
    assert route.call_count == 1
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert TOKEN not in repr(vars(caught.value))
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"finding_id": "id"},
        {"_time": "now"},
        {"created_time": "now", "finding_id": "id"},
        {**CREATED, "finding_id": 123},
        {**CREATED, "finding_id": " "},
        {**CREATED, "risk_score": 2},
        {**CREATED, "finding_id": TOKEN},
    ],
)
def test_invalid_or_credential_echoing_success_is_rejected(respx_mock, body):
    respx_mock.post(ENDPOINT).respond(201, json=body)
    with pytest.raises(
        FindingAPIError, match="Invalid ES finding creation response"
    ) as caught:
        _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)
    assert caught.value.__context__ is None
    assert TOKEN not in str(caught.value)


def test_invalid_json_is_rejected(respx_mock):
    respx_mock.post(ENDPOINT).respond(201, text="<html>not JSON</html>")
    with pytest.raises(FindingAPIError):
        _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)


def test_only_id_is_returned_and_extra_response_fields_are_ignored(respx_mock, caplog):
    caplog.set_level("DEBUG")
    respx_mock.post(ENDPOINT).respond(201, json={**CREATED, "unexpected": TOKEN})
    result = _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)
    assert result == CREATED
    assert TOKEN not in json.dumps(result)
    assert TOKEN not in caplog.text


def test_response_model_matches_schema(es_schema):
    payload = {
        **CREATED,
        "risk_object": "user",
        "risk_object_type": "user",
        "risk_score": "90.0",
        "creator": "analyst",
        "status": "1",
        "urgency": "high",
        "disposition": "6",
        "owner_realname": "Analyst",
        "info_max_time": "now",
        "drilldown_searches": [{}],
        "drilldown_dashboards": [{}],
        "queue_id": "phishing",
        "finding_source": "mail",
        "investigation_type": "default",
        "run_threat_analysis": False,
        "launch_automation": False,
        "automation_rule": "rule",
        "email": {"body": "reported"},
    }
    validator(es_schema, "CreateManualFindingResponse").validate(payload)
    response = CreateFindingResponse.model_validate(payload)
    assert response.created_time == CREATED["_time"]
    assert response.model_dump(by_alias=True, exclude_none=True) == payload
    assert set(payload) == set(
        es_schema["components"]["schemas"]["CreateManualFindingResponse"]["properties"]
    )


def test_existing_bulk_api_has_ordered_results_and_opaque_ids(
    app_with_action, monkeypatch, respx_mock
):
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (BASE_URL, TOKEN))
    route = respx_mock.post(ENDPOINT).mock(
        side_effect=[
            httpx.Response(201, json={**CREATED, "finding_id": "first@@notable@@id"}),
            httpx.Response(403, text=TOKEN),
            httpx.Response(201, json={**CREATED, "finding_id": "third@@notable@@id"}),
        ]
    )
    response = api.create_findings_bulk([MINIMAL, MINIMAL, {}, MINIMAL])
    results = response["results"]
    assert [r["index"] for r in results] == [0, 1, 2, 3]
    assert [r["success"] for r in results] == [True, False, False, True]
    assert [r.get("error_code") for r in results] == [
        None,
        "authorization",
        "validation",
        None,
    ]
    assert [r.get("finding_id") for r in results] == [
        "first@@notable@@id",
        None,
        None,
        "third@@notable@@id",
    ]
    assert response["status"] == "partial"
    assert response["created"] == 2
    assert response["failed"] == 2
    assert response["findings"] == ["first@@notable@@id", "third@@notable@@id"]
    assert response["container_ids"] == []
    assert response["errors"] == [
        {
            "index": 1,
            "error": "ES authorization failed.",
            "error_code": "authorization",
            "status_code": 403,
        },
        {
            "index": 2,
            "error": "Invalid ES finding payload.",
            "error_code": "validation",
            "status_code": None,
        },
    ]
    assert route.call_count == 3
    assert TOKEN not in repr(response)
    assert TOKEN not in json.dumps(response)


@pytest.mark.parametrize(
    "findings, expected_status, expected_created",
    [
        ([], "success", 0),
        ([MINIMAL], "success", 1),
        ([{}], "error", 0),
    ],
)
def test_direct_bulk_empty_success_and_failure(
    app_with_action,
    monkeypatch,
    respx_mock,
    findings,
    expected_status,
    expected_created,
):
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (BASE_URL, TOKEN))
    if expected_created:
        respx_mock.post(ENDPOINT).respond(201, json=CREATED)
    result = api.create_findings_bulk(findings)
    assert result["status"] == expected_status
    assert result["created"] == expected_created
    assert len(result["results"]) == len(findings)
    assert not FindingCreateResult(index=0, error_code="validation").success


@pytest.mark.parametrize("container_ids", [[], [42], [None]])
def test_direct_bulk_rejects_classic_container_ids(
    app_with_action, monkeypatch, respx_mock, container_ids
):
    api = app_with_action.soar_client
    monkeypatch.setattr(api, "_get_es_finding_context", lambda: (BASE_URL, TOKEN))
    with pytest.raises(FindingConfigurationError, match="container IDs"):
        api.create_findings_bulk([MINIMAL], container_ids=container_ids)
    assert not respx_mock.calls


@pytest.mark.parametrize("operation", ["create_finding", "create_findings_bulk"])
def test_context_failure_never_falls_back_to_classic(
    app_with_action, mocker, operation
):
    api = app_with_action.soar_client
    mocker.patch.object(
        api,
        "_get_es_finding_context",
        side_effect=FindingConfigurationError("Execution credentials unavailable."),
    )
    post = mocker.patch.object(api, "post")
    with pytest.raises(FindingConfigurationError):
        getattr(api, operation)(MINIMAL if operation == "create_finding" else [MINIMAL])
    post.assert_not_called()


def test_context_is_resolved_per_operation_without_cached_credentials(
    app_with_action, mocker, respx_mock
):
    api = app_with_action.soar_client
    context = mocker.patch.object(
        api,
        "_get_es_finding_context",
        side_effect=[(BASE_URL, "first-token"), (BASE_URL, "second-token")],
    )
    route = respx_mock.post(ENDPOINT).respond(201, json={**CREATED, "risk_score": "90"})
    assert api.create_finding(MINIMAL) == {**CREATED, "risk_score": "90"}
    assert api.create_finding(MINIMAL) == {**CREATED, "risk_score": "90"}
    assert context.call_count == 2
    assert [call.request.headers["Authorization"] for call in route.calls] == [
        "Bearer first-token",
        "Bearer second-token",
    ]
    assert "Authorization" not in api.client.headers


def test_direct_bulk_retains_existing_limit(app_with_action, mocker, respx_mock):
    api = app_with_action.soar_client
    context = mocker.patch.object(
        api, "_get_es_finding_context", return_value=(BASE_URL, TOKEN)
    )
    with pytest.raises(ValueError, match="Maximum 25"):
        api.create_findings_bulk([MINIMAL] * 26)
    context.assert_not_called()
    assert not respx_mock.calls


@pytest.mark.parametrize(
    "body", [{**CREATED, "_time": TOKEN}, {**CREATED, "email": {"body": TOKEN}}]
)
def test_token_in_known_success_fields_is_rejected(respx_mock, body):
    respx_mock.post(ENDPOINT).respond(201, json=body)
    with pytest.raises(FindingAPIError):
        _create_es_finding(MINIMAL, base_url=BASE_URL, token=TOKEN)
