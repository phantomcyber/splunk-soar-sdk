from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_mock

from soar_sdk.apis.es.findings import CreateFindingResponse
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.finding import Finding
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
        es_base_url="https://es",
        es_session_key="asdf",
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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
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
            finding_id="new_finding", _time="2025-12-09T11:30:00.0000Z", **f.dict()
        ),
    )

    @app_with_action.on_es_poll()
    def on_es_poll_function(
        params: OnESPollParams, client=None
    ) -> Generator[Finding, int | None]:
        yield "This isn't a finding"

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
    result = on_es_poll_actionfailure(params)
    assert result is False


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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
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

    params = OnESPollParams(
        start_time=0, end_time=1, es_base_url="https://es", es_session_key="asdf"
    )
    result = on_es_poll_function(params, client=app_with_action.soar_client)
    assert result is True

    call_args = save_container.call_args[0][0]
    assert call_args["severity"] == "medium"
    assert create_finding.called
