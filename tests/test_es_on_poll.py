from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_mock

from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.finding import Finding, FindingAttachment, FindingEmail
from soar_sdk.params import OnESPollParams

BULK_RESPONSE = {
    "status": "success",
    "created": 1,
    "failed": 0,
    "findings": ["new_finding"],
    "container_ids": [42],
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
    assert create_findings_bulk.called


def test_es_on_poll_yields_invalid_type(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
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
    assert not create_findings_bulk.called


def test_es_on_poll_yields_finding_async_generator(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll yields a Finding and succeeds with an AsyncGenerator."""

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


def test_es_on_poll_finding_data_mapping(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that Finding data is correctly passed to create_findings_bulk."""

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

    call_args = create_findings_bulk.call_args[0][0][0]
    assert call_args["rule_title"] == "Risk threshold exceeded"
    assert call_args["rule_description"] == "User exceeded risk threshold"
    assert call_args["security_domain"] == "threat"
    assert call_args["risk_object"] == "baduser@example.com"
    assert call_args["risk_object_type"] == "user"
    assert call_args["risk_score"] == 100.0
    assert call_args["status"] == "New"
    assert call_args["urgency"] == "high"
    assert call_args["owner"] == "admin"
    assert call_args["disposition"] == "sensitive"
    assert call_args["source"] == ["splunk", "siem"]


def test_es_on_poll_with_attachments(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll pre-creates container, uploads to vault, populates vault links, then creates finding."""
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    save_container = mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "ok", 99),
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.return_value = "vault-abc123"
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Phishing Email",
            run_threat_analysis=True,
            attachments=[
                FindingAttachment(
                    file_name="email.eml", data=b"raw content", is_raw_email=True
                )
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    save_container.assert_called_once()
    create_args = save_container.call_args[0][0]
    assert create_args["name"] == "Phishing Email"
    assert "source_data_identifier" in create_args
    vault_mock.create_attachment.assert_called_once_with(
        99, b"raw content", "email.eml"
    )

    finding_payload = create_findings_bulk.call_args[0][0][0]
    assert finding_payload["email"]["attachments"] == [
        {
            "filename": "email.eml",
            "filesize": len(b"raw content"),
            "url": "https://soar.local/rest/download_attachment?vault_id=vault-abc123",
        }
    ]
    assert finding_payload["email"]["raw_email_link"] == (
        "https://soar.local/rest/download_attachment?vault_id=vault-abc123"
    )

    passed_container_ids = create_findings_bulk.call_args[1].get("container_ids")
    assert passed_container_ids == [99]


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
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value={
            "status": "success",
            "created": 2,
            "failed": 0,
            "findings": ["f1", "f2"],
            "container_ids": [42, 43],
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


def test_es_on_poll_with_ingest_config_defaults(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll applies ingest config defaults to findings."""
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
            "es_drilldown_dashboards": [
                {
                    "app": "DA-ESS-NetworkProtection",
                    "dashboard_id": "dash1",
                    "name": "Dashboard 1",
                }
            ],
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


def test_es_on_poll_vault_upload_failure_continues(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll continues when vault upload fails during pre-creation."""
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "ok", 99),
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.side_effect = Exception("Vault upload failed")
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Phishing Email",
            run_threat_analysis=True,
            attachments=[
                FindingAttachment(
                    file_name="email.eml", data=b"content", is_raw_email=True
                )
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True


def test_es_on_poll_bulk_partial_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll logs warnings when bulk create returns partial errors."""
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value={
            "status": "partial",
            "created": 1,
            "failed": 1,
            "findings": ["f1"],
            "container_ids": [42],
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


def test_es_on_poll_raw_email_link_set_only_for_raw_attachment(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that raw_email_link is set only for is_raw_email attachments, all go to vault."""
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "ok", 99),
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.side_effect = ["vault-eml", "vault-pdf"]
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email with PDF",
            run_threat_analysis=True,
            email=FindingEmail(body="test body"),
            attachments=[
                FindingAttachment(
                    file_name="email.eml", data=b"raw eml", is_raw_email=True
                ),
                FindingAttachment(
                    file_name="report.pdf", data=b"pdf data", is_raw_email=False
                ),
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    assert vault_mock.create_attachment.call_count == 2

    finding_payload = create_findings_bulk.call_args[0][0][0]
    assert finding_payload["email"]["attachments"] == [
        {
            "filename": "email.eml",
            "filesize": len(b"raw eml"),
            "url": "https://soar.local/rest/download_attachment?vault_id=vault-eml",
        },
        {
            "filename": "report.pdf",
            "filesize": len(b"pdf data"),
            "url": "https://soar.local/rest/download_attachment?vault_id=vault-pdf",
        },
    ]
    assert finding_payload["email"]["raw_email_link"] == (
        "https://soar.local/rest/download_attachment?vault_id=vault-eml"
    )

    passed_container_ids = create_findings_bulk.call_args[1].get("container_ids")
    assert passed_container_ids == [99]


def test_es_on_poll_stores_attachments_in_vault_before_finding(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that attachments are stored in the vault before the finding is created."""
    call_order = []

    def track_vault_create(*args, **kwargs):
        call_order.append("vault_create")
        return "vault-id"

    def track_bulk_create(*args, **kwargs):
        call_order.append("bulk_create")
        return BULK_RESPONSE

    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        side_effect=track_bulk_create,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "ok", 99),
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.side_effect = track_vault_create
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email with attachments",
            attachments=[
                FindingAttachment(
                    file_name="email.eml", data=b"raw eml", is_raw_email=True
                ),
                FindingAttachment(
                    file_name="report.pdf", data=b"pdf data", is_raw_email=False
                ),
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert vault_mock.create_attachment.call_count == 2
    vault_mock.create_attachment.assert_any_call(99, b"raw eml", "email.eml")
    vault_mock.create_attachment.assert_any_call(99, b"pdf data", "report.pdf")
    assert call_order == ["vault_create", "vault_create", "bulk_create"]


def test_es_on_poll_container_create_failure_does_not_fail_action(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that container pre-creation failure is non-fatal."""
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        side_effect=Exception("Container error"),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email",
            attachments=[
                FindingAttachment(file_name="email.eml", data=b"raw", is_raw_email=True)
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True


def test_es_on_poll_save_container_returns_failure(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll skips attachment flow when save_container returns failure."""
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(False, "Duplicate container", None),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="Email",
            attachments=[
                FindingAttachment(file_name="email.eml", data=b"raw", is_raw_email=True)
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
    assert create_findings_bulk.call_args[1].get("container_ids") is None


def test_es_on_poll_attachment_creates_email_when_none(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test that email field is created when Finding has attachments but no email set."""
    create_findings_bulk = mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value=BULK_RESPONSE,
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "save_container",
        return_value=(True, "ok", 99),
    )
    vault_mock = MagicMock()
    vault_mock.create_attachment.return_value = "vault-abc"
    mocker.patch.object(
        type(app_with_action.soar_client),
        "vault",
        new_callable=lambda: property(lambda self: vault_mock),
    )
    mocker.patch.object(
        app_with_action.actions_manager,
        "get_soar_base_url",
        return_value="https://soar.local",
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="No email field",
            attachments=[
                FindingAttachment(file_name="file.eml", data=b"data", is_raw_email=True)
            ],
        )

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    finding_payload = create_findings_bulk.call_args[0][0][0]
    assert "email" in finding_payload
    assert finding_payload["email"]["raw_email_link"] == (
        "https://soar.local/rest/download_attachment?vault_id=vault-abc"
    )


def test_es_on_poll_no_container_ids_in_response(
    app_with_action: App, mocker: pytest_mock.MockerFixture
):
    """Test on_es_poll handles bulk response with no container_ids."""
    mocker.patch.object(
        app_with_action.soar_client,
        "create_findings_bulk",
        return_value={
            "status": "success",
            "created": 1,
            "failed": 0,
            "findings": ["f1"],
            "errors": [],
        },
    )
    mock_asset_ingest_config(mocker, app_with_action, {"es_security_domain": "threat"})

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield Finding(rule_title="Test Finding")

    params = OnESPollParams(start_time=0, end_time=1)
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True
