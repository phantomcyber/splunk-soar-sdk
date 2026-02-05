from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_mock

from soar_sdk.apis.es.findings import CreateFindingResponse
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.finding import Finding, FindingAttachment
from soar_sdk.params import OnESPollParams


def test_es_on_poll_decoration_fails_when_used_more_than_once(app_with_action: App):
    """Test that the on_es_poll decorator can only be used once per app."""

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield (
            Finding(
                rule_title="Test",
                rule_description="Test",
                security_domain="threat",
                risk_object="test",
                risk_object_type="user",
                risk_score=100.0,
            ),
            [],
        )

    with pytest.raises(TypeError, match=r"on_es_poll.+once per"):

        @app_with_action.on_es_poll()
        def second_on_es_poll(
            params: OnESPollParams, client=None
        ) -> Generator[Finding, int | None]:
            yield (
                Finding(
                    rule_title="Test2",
                    rule_description="Test2",
                    security_domain="threat",
                    risk_object="test2",
                    risk_object_type="user",
                    risk_score=100.0,
                ),
                [],
            )


def test_es_on_poll_decoration_fails_when_not_generator(app_with_action: App):
    """Test that the on_es_poll decorator requires a generator function."""

    with pytest.raises(TypeError, match="must be a Generator"):

        @app_with_action.on_es_poll()
        def on_es_poll_function(params: OnESPollParams, client=None):
            return (
                Finding(
                    rule_title="Test",
                    rule_description="Test",
                    security_domain="threat",
                    risk_object="test",
                    risk_object_type="user",
                    risk_score=100.0,
                ),
                [],
            )


def test_es_on_poll_decoration_fails_with_wrong_typeargs(app_with_action: App):
    """Test that the on_es_poll decorator requires a generator function."""

    with pytest.raises(
        TypeError,
        match="should have yield type <class 'soar_sdk.models.finding.Finding'>",
    ):

        @app_with_action.on_es_poll()
        def on_es_poll_function(
            params: OnESPollParams, client=None
        ) -> Generator[str, int | None]:
            yield Finding(
                rule_title="Test",
                rule_description="Test",
                security_domain="threat",
                risk_object="test",
                risk_object_type="user",
                risk_score=100.0,
            )

    with pytest.raises(
        TypeError,
        match="should have send type int | None",
    ):

        @app_with_action.on_es_poll()
        def on_es_poll_function(
            params: OnESPollParams, client=None
        ) -> Generator[Finding, str]:
            yield Finding(
                rule_title="Test",
                rule_description="Test",
                security_domain="threat",
                risk_object="test",
                risk_object_type="user",
                risk_score=100.0,
            )


def test_es_on_poll_param_validation_error(app_with_action: App):
    """Test on_es_poll handles parameter validation errors and returns False."""

    @app_with_action.on_es_poll()
    def on_es_poll_function(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score=100.0,
        )

    invalid_params = "invalid"
    result = on_es_poll_function(invalid_params)
    assert result is False


def test_es_on_poll_raises_exception_propagates(app_with_action: App):
    """Test that exceptions raised in the on_es_poll function are handled and return False."""

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams,
    ) -> Generator[Finding, int | None]:
        raise ValueError("poll error")
        yield  # pragma: no cover

    params = OnESPollParams(
        start_time=0,
        end_time=1,
        container_count=10,
    )

    result = on_es_poll_function(params)
    assert result is False


def test_es_on_poll_yields_finding_success(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll yields a Finding and succeeds."""

    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Risk threshold exceeded",
            rule_description="User exceeded risk threshold",
            security_domain="threat",
            risk_object="baduser@example.com",
            risk_object_type="user",
            risk_score=100.0,
            status="New",
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert save_container.call_count == 1
    assert create_finding.called


def test_es_on_poll_yields_invalid_type(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield "This isn't a finding"

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert not save_container.called
    assert not create_finding.called


def test_es_on_poll_throws_when_fail_to_create_container(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(False, "Error", None),
    )
    mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Risk threshold exceeded",
            rule_description="User exceeded risk threshold",
            security_domain="threat",
            risk_object="baduser@example.com",
            risk_object_type="user",
            risk_score=100.0,
            status="New",
        )

    params = OnESPollParams(start_time=0, end_time=1)
    with pytest.raises(ActionFailure, match="Failed to create container"):
        on_es_poll_function(params, client=app_with_action.soar_client)


def test_es_on_poll_yields_finding_async_generator(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll yields a Finding and succeeds with an AsyncGenerator."""

    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    async def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> AsyncGenerator[Finding, int | None]:
        yield Finding(
            rule_title="Risk threshold exceeded",
            rule_description="User exceeded risk threshold",
            security_domain="threat",
            risk_object="baduser@example.com",
            risk_object_type="user",
            risk_score=100.0,
            status="New",
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert save_container.call_count == 1
    assert create_finding.called


def test_es_on_poll_failure(app_with_action: App):
    """Test on_es_poll handles ActionFailure correctly."""

    @app_with_action.on_es_poll()
    def on_es_poll_actionfailure(
        params: OnESPollParams,
    ) -> Generator[Finding, int | None]:
        raise ActionFailure("failmsg")
        yield  # pragma: no cover

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_actionfailure(params)
    assert result is False


def test_on_es_poll_params_is_manual_poll():
    """Test OnESPollParams.is_manual_poll detection."""
    from soar_sdk.params import MAX_COUNT_VALUE

    params = OnESPollParams(start_time=0, end_time=1, container_count=10)
    assert params.is_manual_poll() is True

    params = OnESPollParams(start_time=0, end_time=1, container_count=MAX_COUNT_VALUE)
    assert params.is_manual_poll() is False

    params = OnESPollParams(start_time=0, end_time=1)
    assert params.is_manual_poll() is False


def test_es_on_poll_decoration_with_meta(app_with_action: App):
    """Test that the on_es_poll decorator properly sets up metadata."""

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams,
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score=100.0,
        )

    action = app_with_action.actions_manager.get_action("on_es_poll")
    assert action is not None
    assert action.meta.action == "on es poll"
    assert action == on_es_poll_function


def test_es_on_poll_actionmeta_dict_output_empty(app_with_action: App):
    """Test that OnESPollActionMeta.dict returns output as an empty list."""

    @app_with_action.on_es_poll()
    def on_es_poll_function(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Test",
            rule_description="Test",
            security_domain="threat",
            risk_object="test",
            risk_object_type="user",
            risk_score=100.0,
        )

    action = app_with_action.actions_manager.get_action("on_es_poll")
    meta_dict = action.meta.model_dump()
    assert "output" in meta_dict
    assert meta_dict["output"] == []


def test_es_on_poll_container_data_mapping(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that Finding data is correctly mapped to Container fields."""

    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Risk threshold exceeded",
            rule_description="User exceeded risk threshold",
            security_domain="threat",
            risk_object="baduser@example.com",
            risk_object_type="user",
            risk_score=100.0,
            status="New",
            urgency="high",
            owner="admin",
            disposition="sensitive",
            source=["splunk", "siem"],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = save_container.call_args[0][0]
    assert call_args["name"] == "Risk threshold exceeded"
    assert call_args["description"] == "User exceeded risk threshold"
    assert call_args["severity"] == "high"
    assert call_args["status"] == "New"
    assert call_args["owner_id"] == "admin"
    assert call_args["sensitivity"] == "sensitive"
    assert call_args["tags"] == ["splunk", "siem"]
    assert call_args["data"]["security_domain"] == "threat"
    assert call_args["data"]["risk_score"] == 100.0
    assert call_args["data"]["risk_object"] == "baduser@example.com"
    assert call_args["data"]["risk_object_type"] == "user"
    assert create_finding.called


def test_es_on_poll_container_data_mapping_defaults(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that Finding data uses defaults when optional fields are not provided."""

    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Risk threshold exceeded",
            rule_description="User exceeded risk threshold",
            security_domain="threat",
            risk_object="baduser@example.com",
            risk_object_type="user",
            risk_score=100.0,
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = save_container.call_args[0][0]
    assert call_args["severity"] == "medium"
    assert create_finding.called


def test_es_on_poll_pairing_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles ES pairing failure."""
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(False, None, "ES pairing not configured"),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_no_token(app_with_action: App, mocker: pytest_mock.MockerFixture):
    """Test on_es_poll handles missing ES token."""
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": ""},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_with_attachments(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll uploads attachments when run_threat_analysis is True."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    upload_mock = mocker.patch("soar_sdk.apis.es.findings.Findings.upload_attachment")
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Phishing Email",
            run_threat_analysis=True,
            attachments=[FindingAttachment(file_name="email.eml", data=b"raw content")],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    upload_mock.assert_called_once_with("new_finding", "email.eml", b"raw content")


def test_es_on_poll_missing_security_domain(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll fails when es_security_domain is not configured."""
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_with_finding_limit(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll stops after reaching container_count limit."""
    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    findings_yielded = 0

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        nonlocal findings_yielded
        while True:
            findings_yielded += 1
            yield Finding(rule_title=f"Finding {findings_yielded}")

    params = OnESPollParams(start_time=0, end_time=1, container_count=2)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert save_container.call_count == 2


def test_es_on_poll_with_ingest_config_defaults(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll applies ingest config defaults to findings."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={
            "ingest": {
                "es_security_domain": "network",
                "es_urgency": "high",
                "es_run_threat_analysis": True,
                "es_launch_automation": True,
            }
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_finding.call_args[0][0]
    assert call_args.security_domain == "network"
    assert call_args.urgency == "high"
    assert call_args.run_threat_analysis is True
    assert call_args.launch_automation is True


def test_es_on_poll_with_invalid_drilldown_searches(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles invalid drilldown_searches gracefully."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={
            "ingest": {
                "es_security_domain": "threat",
                "es_drilldown_searches": [{"invalid": "data"}],
            }
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_finding.call_args[0][0]
    assert call_args.drilldown_searches is None


def test_es_on_poll_with_invalid_drilldown_dashboards(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles invalid drilldown_dashboards gracefully."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={
            "ingest": {
                "es_security_domain": "threat",
                "es_drilldown_dashboards": [{"invalid": "data"}],
            }
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_finding.call_args[0][0]
    assert call_args.drilldown_dashboards is None


def test_es_on_poll_with_drilldown_list_format(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll accepts drilldowns as list (not JSON string)."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={
            "ingest": {
                "es_security_domain": "threat",
                "es_drilldown_searches": [
                    {
                        "name": "search1",
                        "search": "index=main",
                        "earliest": "-1h",
                        "latest": "now",
                    }
                ],
                "es_drilldown_dashboards": [
                    {"dashboard": "dash1", "name": "Dashboard 1"}
                ],
            }
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_finding.call_args[0][0]
    assert call_args.drilldown_searches is not None
    assert call_args.drilldown_dashboards is not None


def test_es_on_poll_finding_overrides_config_defaults(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that Finding values override ingest config defaults."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_finding = mocker.patch(
        "soar_sdk.apis.es.findings.Findings.create",
        side_effect=lambda f: CreateFindingResponse(
            finding_id="new_finding",
            _time="2025-12-09T11:30:00.0000Z",
            **f.model_dump(),
        ),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={
            "ingest": {
                "es_security_domain": "network",
                "es_urgency": "high",
            }
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Test Finding",
            security_domain="threat",
            urgency="critical",
            run_threat_analysis=True,
            launch_automation=True,
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_finding.call_args[0][0]
    assert call_args.security_domain == "threat"
    assert call_args.urgency == "critical"
    assert call_args.run_threat_analysis is True
    assert call_args.launch_automation is True


def test_es_on_poll_generator_exception(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles general exceptions during iteration."""
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        raise RuntimeError("Unexpected error during iteration")
        yield

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_action_failure_during_iteration(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles ActionFailure during iteration and sets action name."""
    mocker.patch.object(
        app_with_action.soar_client,
        "get_es_pairing",
        return_value=(
            True,
            {"es_url": "https://es", "rest_port": 8089, "es_token": "token123"},
            "OK",
        ),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_config",
        return_value={"ingest": {"es_security_domain": "threat"}},
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        raise ActionFailure("Custom action failure message")
        yield

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


class TestGetESPairing:
    """Tests for SOARClient.get_es_pairing method."""

    def test_get_es_pairing_non_200_status(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing returns failure on non-200 status code."""
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mocker.patch.object(
            app_with_action.soar_client, "get", return_value=mock_response
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is False
        assert pairing is None
        assert "status: 404" in message

    def test_get_es_pairing_not_paired(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing returns failure when not paired."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_paired": False}
        mocker.patch.object(
            app_with_action.soar_client, "get", return_value=mock_response
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is False
        assert pairing is None
        assert "No active ES pairing found" in message

    def test_get_es_pairing_empty_pairing_data(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing returns failure when pairing data is empty."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_paired": True, "pairing": {}}
        mocker.patch.object(
            app_with_action.soar_client, "get", return_value=mock_response
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is False
        assert pairing is None
        assert "ES pairing data is empty" in message

    def test_get_es_pairing_success_with_token(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing returns success with token."""
        pairing_response = mocker.Mock()
        pairing_response.status_code = 200
        pairing_response.json.return_value = {
            "is_paired": True,
            "pairing": {"es_url": "https://es.example.com", "rest_port": 8089},
        }

        token_response = mocker.Mock()
        token_response.status_code = 200
        token_response.json.return_value = {"token": "secret_token_123"}

        mocker.patch.object(
            app_with_action.soar_client,
            "get",
            side_effect=[pairing_response, token_response],
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is True
        assert pairing["es_url"] == "https://es.example.com"
        assert pairing["rest_port"] == 8089
        assert pairing["es_token"] == "secret_token_123"
        assert "successfully" in message

    def test_get_es_pairing_token_fetch_fails(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing succeeds even when token fetch fails."""
        pairing_response = mocker.Mock()
        pairing_response.status_code = 200
        pairing_response.json.return_value = {
            "is_paired": True,
            "pairing": {"es_url": "https://es.example.com", "rest_port": 8089},
        }

        def get_side_effect(endpoint, **kwargs):
            if "pairing" in endpoint:
                return pairing_response
            raise ConnectionError("Token fetch failed")

        mocker.patch.object(
            app_with_action.soar_client, "get", side_effect=get_side_effect
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is True
        assert pairing["es_url"] == "https://es.example.com"
        assert "es_token" not in pairing
        assert "successfully" in message

    def test_get_es_pairing_token_non_200(
        self, app_with_action: App, mocker: pytest_mock.MockerFixture
    ):
        """Test get_es_pairing succeeds with token endpoint returning non-200."""
        pairing_response = mocker.Mock()
        pairing_response.status_code = 200
        pairing_response.json.return_value = {
            "is_paired": True,
            "pairing": {"es_url": "https://es.example.com", "rest_port": 8089},
        }

        token_response = mocker.Mock()
        token_response.status_code = 403

        mocker.patch.object(
            app_with_action.soar_client,
            "get",
            side_effect=[pairing_response, token_response],
        )

        success, pairing, message = app_with_action.soar_client.get_es_pairing()

        assert success is True
        assert pairing["es_url"] == "https://es.example.com"
        assert "es_token" not in pairing
