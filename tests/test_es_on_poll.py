from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_mock

from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.finding import Finding, FindingAttachment
from soar_sdk.params import OnESPollParams

BULK_RESPONSE = {
    "status": "success",
    "created": 1,
    "failed": 0,
    "findings": ["new_finding"],
    "errors": [],
}


def mock_asset_ingest_config(mocker, app, ingest_config):
    """Mock the soar_client.get() call to return asset configuration.

    The ingest config is fetched via REST API from /rest/asset/{asset_id},
    so we need to mock the HTTP response.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {"configuration": {"ingest": ingest_config}}
    mocker.patch.object(app.soar_client, "get", return_value=mock_response)


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


def test_es_on_poll_raises_exception_propagates(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that exceptions raised in the on_es_poll function are handled and return False."""
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    assert create_findings_bulk.called


def test_es_on_poll_yields_invalid_type(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield "This isn't a finding"

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert not save_container.called
    assert not create_findings_bulk.called


def test_es_on_poll_throws_when_fail_to_create_container(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(False, "Error", None),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    assert create_findings_bulk.called


def test_es_on_poll_failure(app_with_action: App, mocker: pytest_mock.MockerFixture):
    """Test on_es_poll handles ActionFailure correctly."""
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    assert create_findings_bulk.called


def test_es_on_poll_with_attachments(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll uploads attachments when run_threat_analysis is True."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    upload_mock = mocker.patch.object(
        app_with_action.soar_client,
        "upload_finding_attachment",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    upload_mock.assert_called_once_with(
        "new_finding",
        "email.eml",
        b"raw content",
        source_type="Incident",
        is_raw_email=True,
    )


def test_es_on_poll_missing_security_domain(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll fails when es_security_domain is not configured."""
    mock_asset_ingest_config(mocker, app_with_action, {})

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
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value={
            "status": "success",
            "created": 2,
            "failed": 0,
            "findings": ["f1", "f2"],
            "errors": [],
        },
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(
        mocker,
        app_with_action,
        {
            "es_security_domain": "network",
            "es_urgency": "high",
            "es_run_threat_analysis": True,
            "es_launch_automation": True,
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

    call_args = create_findings_bulk.call_args[0][0][0]
    assert call_args["security_domain"] == "network"
    assert call_args["urgency"] == "high"
    assert call_args["run_threat_analysis"] is True
    assert call_args["launch_automation"] is True


def test_es_on_poll_with_invalid_drilldown_searches(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll fails with invalid drilldown_searches."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(
        mocker,
        app_with_action,
        {
            "es_security_domain": "threat",
            "es_drilldown_searches": [{"invalid": "data"}],
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_with_invalid_drilldown_dashboards(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll fails with invalid drilldown_dashboards."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(
        mocker,
        app_with_action,
        {
            "es_security_domain": "threat",
            "es_drilldown_dashboards": [{"invalid": "data"}],
        },
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_with_drilldown_list_format(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll accepts drilldowns as list (not JSON string)."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(
        mocker,
        app_with_action,
        {
            "es_security_domain": "threat",
            "es_drilldown_searches": [
                {
                    "name": "search1",
                    "search": "index=main",
                    "earliest": "-1h",
                    "latest": "now",
                }
            ],
            "es_drilldown_dashboards": [{"dashboard": "dash1", "name": "Dashboard 1"}],
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

    call_args = create_findings_bulk.call_args[0][0][0]
    assert call_args.get("drilldown_searches") is not None
    assert call_args.get("drilldown_dashboards") is not None


def test_es_on_poll_finding_overrides_config_defaults(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that Finding values override ingest config defaults."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mock_asset_ingest_config(
        mocker,
        app_with_action,
        {
            "es_security_domain": "network",
            "es_urgency": "high",
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

    call_args = create_findings_bulk.call_args[0][0][0]
    assert call_args["security_domain"] == "threat"
    assert call_args["urgency"] == "critical"
    assert call_args["run_threat_analysis"] is True
    assert call_args["launch_automation"] is True


def test_es_on_poll_generator_exception(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles general exceptions during iteration."""
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

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
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        raise ActionFailure("Custom action failure message")
        yield

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_create_findings_bulk_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles create_findings_bulk exception."""
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        side_effect=Exception("API error"),
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is False


def test_es_on_poll_upload_attachment_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll continues when upload_finding_attachment fails."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "upload_finding_attachment",
        side_effect=Exception("Upload failed"),
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Phishing Email",
            run_threat_analysis=True,
            attachments=[FindingAttachment(file_name="email.eml", data=b"content")],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True


def test_es_on_poll_bulk_partial_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll logs warnings when bulk create returns partial errors."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value={
            "status": "partial",
            "created": 1,
            "failed": 1,
            "findings": ["f1"],
            "errors": [
                {"index": 1, "rule_title": "Bad Finding", "error": "invalid field"}
            ],
        },
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Good Finding")
        yield Finding(rule_title="Bad Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True


def test_es_on_poll_no_finding_source_when_names_empty(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that finding_source is not set when app name and asset name are both empty."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    app_with_action.app_meta_info["name"] = ""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "name": "",
        "configuration": {"ingest": {"es_security_domain": "threat"}},
    }
    mocker.patch.object(app_with_action.soar_client, "get", return_value=mock_response)

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = create_findings_bulk.call_args[0][0][0]
    assert call_args.get("finding_source") is None


def test_es_on_poll_only_uploads_raw_email_to_es(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that only is_raw_email attachments are uploaded to ES findings."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    upload_mock = mocker.patch.object(
        app_with_action.soar_client,
        "upload_finding_attachment",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email with PDF",
            run_threat_analysis=True,
            attachments=[
                FindingAttachment(file_name="email.eml", data=b"raw eml"),
                FindingAttachment(
                    file_name="report.pdf", data=b"pdf data", is_raw_email=False
                ),
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    upload_mock.assert_called_once_with(
        "new_finding",
        "email.eml",
        b"raw eml",
        source_type="Incident",
        is_raw_email=True,
    )


def test_es_on_poll_stores_attachments_in_container_vault(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that attachments are stored in the container vault after container creation."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    vault_mock = MagicMock()
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email with attachments",
            attachments=[
                FindingAttachment(file_name="email.eml", data=b"raw eml"),
                FindingAttachment(
                    file_name="report.pdf", data=b"pdf data", is_raw_email=False
                ),
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert vault_mock.create_attachment.call_count == 2
    vault_mock.create_attachment.assert_any_call(42, b"raw eml", "email.eml")
    vault_mock.create_attachment.assert_any_call(42, b"pdf data", "report.pdf")


def test_es_on_poll_vault_failure_does_not_fail_action(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that vault attachment failure is non-fatal."""
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "Created", 42),
    )
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.side_effect = Exception("Vault error")
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email",
            attachments=[FindingAttachment(file_name="email.eml", data=b"raw")],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
