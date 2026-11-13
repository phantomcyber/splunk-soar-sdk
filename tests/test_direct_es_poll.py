import json
import sys
import traceback
from collections.abc import AsyncGenerator, Generator
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from soar_sdk.apis._es_findings import _get_runtime_es_context
from soar_sdk.asset_state import AssetState
from soar_sdk.exceptions import FindingConfigurationError
from soar_sdk.models.finding import Finding
from soar_sdk.params import OnESPollParams

URL = "https://es.example:8089"
ENDPOINT = URL + "/servicesNS/nobody/missioncontrol/public/v2/findings"
TOKEN = "private-runtime-secret"


@pytest.fixture
def direct_app(app_with_action, monkeypatch, mocker):
    app = app_with_action
    monkeypatch.setitem(
        sys.modules,
        "es_poll_api",
        SimpleNamespace(get_es_context=lambda: (URL, TOKEN)),
    )
    app._es_ingest_config = {"es_security_domain": "threat"}
    app.asset._ingest_state = None
    mocker.patch.object(
        app.soar_client, "get", side_effect=AssertionError("SOAR REST called")
    )
    mocker.patch.object(
        app.actions_manager,
        "save_container",
        side_effect=AssertionError("SOAR container called"),
    )
    mocker.patch.object(app.actions_manager, "add_result")
    return app


def outcome(app):
    return app.actions_manager.add_result.call_args.args[0]


@pytest.mark.parametrize("raw", [None, {"identifier": "on_es_poll", "config": None}])
def test_app_handle_retains_input_validation(direct_app, raw):
    with pytest.raises(ValidationError):
        direct_app.handle(json.dumps(raw))


def test_app_handle_preserves_es_settings_and_returns_ids(
    direct_app, simple_action_input, respx_mock, mocker
):
    app = direct_app
    mocker.stop(app.actions_manager.add_result)
    route = respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "through-handle"}
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        assert params.access_token.get_secret_value() == TOKEN
        yield Finding(rule_title="through-handle")

    raw = simple_action_input.model_dump()
    raw["identifier"] = "on_es_poll"
    raw["action"] = "on es poll"
    raw["parameters"] = [{}]
    raw["config"]["ingest"] = {"es_security_domain": "threat", "es_urgency": "high"}
    returned = app.handle(json.dumps(raw))
    result = app.actions_manager.get_action_results()[-1]
    assert result.get_status()
    assert result.get_data()[0]["finding_id"] == "through-handle"
    assert json.loads(route.calls[0].request.content)["urgency"] == "high"
    assert TOKEN not in returned
    assert "access_token" not in returned
    assert app._raw_asset_config.get("ingest") is None


@pytest.mark.parametrize(
    "count, limit, expected", [(0, None, 0), (1, None, 1), (28, None, 28), (3, 1, 1)]
)
def test_poll_creates_findings_without_soar_calls(
    direct_app, respx_mock, count, limit, expected
):
    app = direct_app
    seen = []
    closed = []

    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            201, json={"_time": "now", "finding_id": f"finding-{len(seen)}"}
        )

    route = respx_mock.post(ENDPOINT).mock(side_effect=respond)

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        assert params.base_url == URL
        assert params.access_token.get_secret_value() == TOKEN
        assert TOKEN not in repr(params)
        assert "base_url" not in params.model_dump()
        assert "access_token" not in params.model_dump()
        try:
            for index in range(count):
                assert (yield Finding(rule_title=f"mail-{index}")) is None
        finally:
            closed.append(True)

    params = (
        OnESPollParams() if limit is None else OnESPollParams(container_count=limit)
    )
    assert poll(params)
    result = outcome(app)
    assert result.get_summary()["created"] == expected
    assert result.get_summary()["status"] == "success"
    assert route.call_count == expected
    assert [entry["finding_id"] for entry in result.get_data()] == [
        f"finding-{i + 1}" for i in range(expected)
    ]
    assert [entry["index"] for entry in result.get_data()] == list(range(expected))
    assert all(payload["security_domain"] == "threat" for payload in seen)
    assert closed == [True]
    assert params.base_url is None
    assert params.access_token is None
    assert TOKEN not in repr(vars(result))
    assert not {"base_url", "access_token"} & OnESPollParams._to_json_schema().keys()
    assert (
        not {"base_url", "access_token"}
        & OnESPollParams.model_json_schema()["properties"].keys()
    )


def test_async_poll_uses_same_direct_transport(direct_app, respx_mock, monkeypatch):
    app = direct_app
    monkeypatch.setitem(
        sys.modules,
        "es_poll_api",
        SimpleNamespace(get_es_context=lambda: (URL, SecretStr(TOKEN))),
    )
    route = respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "async-id"}
    )
    closed = []

    @app.on_es_poll()
    async def poll(params: OnESPollParams) -> AsyncGenerator[Finding, int | None]:
        try:
            yield Finding(
                rule_title="async", security_domain="identity", urgency="high"
            )
        finally:
            closed.append(True)

    assert poll(OnESPollParams())
    assert outcome(app).get_data()[0]["finding_id"] == "async-id"
    assert json.loads(route.calls[0].request.content)["security_domain"] == "identity"
    assert closed == [True]


def test_direct_poll_preserves_explicit_analysis_and_automation_flags(
    direct_app, respx_mock
):
    from soar_sdk.models.finding import FindingEmail

    app = direct_app
    route = respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "flagged"}
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield Finding(
            rule_title="explicit",
            run_threat_analysis=True,
            launch_automation=True,
            automation_rule="playbook",
            email=FindingEmail(raw_email_link="https://files.example/raw"),
        )

    assert poll(OnESPollParams())
    payload = json.loads(route.calls[0].request.content)
    assert payload["run_threat_analysis"] is True
    assert payload["launch_automation"] is True


def test_partial_failures_are_reported_and_checkpoint_advances(direct_app, respx_mock):
    app = direct_app
    state = AssetState(app.actions_manager, "ingest", "1")
    app.asset._ingest_state = state
    route = respx_mock.post(ENDPOINT).mock(
        side_effect=[
            httpx.Response(201, json={"_time": "now", "finding_id": "first"}),
            httpx.Response(403, text=TOKEN),
            httpx.ReadTimeout(TOKEN),
            httpx.Response(503, text=TOKEN),
            httpx.Response(201, json={"_time": "now", "finding_id": "last"}),
        ]
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        for index in range(5):
            yield Finding(rule_title=str(index))
        state["cursor"] = 5

    assert poll(OnESPollParams())
    result = outcome(app)
    assert result.get_summary() == {
        "status": "partial",
        "created": 2,
        "failed": 3,
        "polling_failed": False,
        "attachments_uploaded": 0,
        "attachments_failed": 0,
        "links_queued": 0,
        "links_failed": 0,
    }
    assert [row.get("error_code") for row in result.get_data()] == [
        None,
        "authorization",
        "timeout",
        "unavailable",
        None,
    ]
    assert route.call_count == 5
    assert state["cursor"] == 5
    assert not state.in_transaction
    assert TOKEN not in repr(vars(result))


@pytest.mark.parametrize("all_invalid", [False, True])
def test_invalid_items_do_not_abort_poll(direct_app, respx_mock, all_invalid):
    app = direct_app
    route = respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "valid"}
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield "invalid"
        yield Finding(rule_title="invalid data", additional_fields={"x": object()})
        if not all_invalid:
            yield Finding(rule_title="valid")

    assert poll(OnESPollParams()) is (not all_invalid)
    result = outcome(app)
    assert result.get_summary()["failed"] == 2
    assert result.get_summary()["created"] == (0 if all_invalid else 1)
    assert route.call_count == (0 if all_invalid else 1)
    assert "private contents" not in repr(vars(result))


@pytest.mark.parametrize(
    "failure", ["iteration", "close", "begin", "commit", "rollback"]
)
def test_handler_and_state_errors_are_safe_and_close_execution(
    direct_app, mocker, failure, caplog
):
    app = direct_app
    state = AssetState(app.actions_manager, "ingest", "1")
    app.asset._ingest_state = state
    mocker.patch.object(
        app.soar_client,
        "create_findings_bulk",
        return_value={"results": [{"index": 0, "success": True, "finding_id": "id"}]},
    )
    if failure in {"begin", "commit", "rollback"}:
        mocker.patch.object(
            state,
            "begin_transaction" if failure == "begin" else failure,
            side_effect=RuntimeError(TOKEN),
        )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        try:
            if failure in {"iteration", "rollback"}:
                state["cursor"] = 99
                raise RuntimeError(TOKEN)
            if failure == "close":
                yield Finding(rule_title="close")
            yield from ()
        finally:
            if failure == "close":
                raise RuntimeError(TOKEN)

    params = (
        OnESPollParams(container_count=1) if failure == "close" else OnESPollParams()
    )
    assert not poll(params)
    assert outcome(app).get_summary()["polling_failed"]
    assert TOKEN not in repr(vars(outcome(app)))
    assert TOKEN not in caplog.text
    assert params.access_token is None


def test_runtime_context_failure_never_enters_handler(direct_app, monkeypatch):
    import sys

    app = direct_app
    monkeypatch.setitem(
        sys.modules,
        "es_poll_api",
        SimpleNamespace(
            get_es_context=lambda: (_ for _ in ()).throw(RuntimeError(TOKEN))
        ),
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        raise AssertionError("handler called")
        yield

    assert not poll(OnESPollParams())
    assert TOKEN not in outcome(app).get_message()


@pytest.mark.parametrize(
    "error", [ModuleNotFoundError(TOKEN, name="dependency"), RuntimeError(TOKEN)]
)
def test_broken_bridge_import_does_not_expose_secrets(mocker, error):
    mocker.patch("soar_sdk.apis._es_findings.import_module", side_effect=error)
    with pytest.raises(FindingConfigurationError) as caught:
        _get_runtime_es_context()
    assert caught.value.__context__ is None
    assert TOKEN not in "".join(traceback.format_exception(caught.value))


def test_non_es_runtime_retains_classic_context(monkeypatch):
    import sys

    monkeypatch.setitem(
        sys.modules, "es_poll_api", SimpleNamespace(get_es_context=lambda: None)
    )
    assert _get_runtime_es_context() is None


@pytest.fixture
def poll_attachments(direct_app, monkeypatch, mocker):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from soar_sdk.exceptions import AttachmentUploadError
    from soar_sdk.models.attachment_upload import AttachmentUploadResult

    bridge = SimpleNamespace(
        get_upload_targets=mocker.Mock(),
        associate_subject_attachments=mocker.Mock(return_value="queue-message"),
    )
    issued = []
    paths = []
    events = []

    def reserve(names, key):
        UUID(key)
        events.append("reserve")
        targets = []
        for name in names:
            identifier = str(UUID(int=len(issued) + 1))
            issued.append(identifier)
            targets.append(
                {
                    "attachment_id": identifier,
                    "file_name": name,
                    "upload_url": "https://s3.example/upload?signature=signed-secret",
                    "form_fields": [{"name": "key", "value": "form-secret"}],
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5),
                    "max_size_bytes": 10000,
                }
            )
        return targets

    bridge.get_upload_targets.side_effect = reserve
    monkeypatch.setitem(sys.modules, "attachment_api", bridge)
    monkeypatch.setattr(
        sys.modules["es_poll_api"],
        "get_attachment_reference_base_url",
        lambda: URL + "/attachment-proxy",
        raising=False,
    )

    def upload(path, target, **kwargs):
        paths.append(path)
        events.append("upload")
        if target.file_name == "failed.eml" or not path.exists():
            raise AttachmentUploadError(
                "Upload failed.", error_code="file", attachment_id=target.attachment_id
            )
        assert path.read_bytes() == b"private-file-contents"
        return AttachmentUploadResult(
            attachment_id=target.attachment_id,
            file_name=target.file_name,
            size_bytes=path.stat().st_size,
        )

    upload_mock = mocker.patch.object(
        direct_app.soar_client.attachments, "upload_file", side_effect=upload
    )
    return SimpleNamespace(
        bridge=bridge,
        issued=issued,
        paths=paths,
        events=events,
        upload_mock=upload_mock,
    )


def attached_finding(title="mail", names=("email.eml",), *, raw=True):
    from soar_sdk.models.finding import FindingAttachment

    return Finding(
        rule_title=title,
        attachments=[
            FindingAttachment(
                file_name=name,
                data=b"private-file-contents",
                is_raw_email=raw,
            )
            for name in names
        ],
    )


@pytest.mark.parametrize("link_fails", [False, True])
def test_poll_upload_create_and_link_preserve_ownership(
    direct_app, poll_attachments, respx_mock, link_fails, caplog
):
    from pathlib import Path

    from jsonschema import Draft4Validator, FormatChecker

    app = direct_app
    context = poll_attachments
    seen = []
    schemas = json.loads(
        (Path(__file__).parent / "fixtures/es_findings_openapi.json").read_text()
    )
    # Use the same captured OpenAPI definition as the transport contract tests.
    if link_fails:
        context.bridge.associate_subject_attachments.side_effect = RuntimeError(TOKEN)

    def create(request):
        assert context.events.count("upload") == 4
        context.events.append("create")
        payload = json.loads(request.content)
        Draft4Validator(
            {**schemas, "$ref": "#/components/schemas/CreateManualFindingRequest"},
            format_checker=FormatChecker(),
        ).validate(payload)
        seen.append(payload)
        index = len(seen)
        if index == 2:
            return httpx.Response(503, text=TOKEN)
        return httpx.Response(
            201, json={"_time": "now", "finding_id": f"finding-{index}"}
        )

    respx_mock.post(ENDPOINT).mock(side_effect=create)
    items = [
        attached_finding(names=("email.eml", "failed.eml")),
        attached_finding("rejected"),
        attached_finding("last"),
        Finding(rule_title="no files"),
    ]

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield from items

    assert poll(OnESPollParams())
    assert context.bridge.get_upload_targets.call_count == 1
    assert context.bridge.get_upload_targets.call_args.args[0] == [
        "email.eml",
        "failed.eml",
        "email.eml",
        "email.eml",
    ]
    expected = [
        {"subject_id": "finding-1", "attachment_ids": [context.issued[0]]},
        {"subject_id": "finding-3", "attachment_ids": [context.issued[3]]},
    ]
    context.bridge.associate_subject_attachments.assert_called_once_with(expected)
    assert len(seen[0]["email"]["attachments"]) == 1
    assert (
        seen[0]["email"]["raw_email_link"]
        == URL + "/attachment-proxy?attachment_id=" + context.issued[0]
    )
    assert "email" not in seen[3]
    assert all(not path.exists() for path in context.paths)
    rows = outcome(app).get_data()
    assert rows[0]["attachment_links"]["status"] == (
        "failed" if link_fails else "queued"
    )
    assert "attachment_links" not in rows[1]
    summary = outcome(app).get_summary()
    assert summary["created"] == 3
    assert summary["failed"] == 1
    assert summary["attachments_uploaded"] == 3
    assert summary["attachments_failed"] == 1
    assert summary["links_queued"] == (0 if link_fails else 2)
    assert summary["links_failed"] == (2 if link_fails else 0)
    assert items[0].email is None
    rendered = repr(vars(outcome(app))) + caplog.text
    for secret in (TOKEN, "private-file-contents", "signed-secret", "form-secret"):
        assert secret not in rendered


@pytest.mark.parametrize("count", [1, 20, 21, 41])
def test_poll_attachment_reservations_are_bounded_and_unique(
    direct_app, poll_attachments, respx_mock, count
):
    app = direct_app
    respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "created"}
    )

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield attached_finding(names=("same.eml",) * count, raw=False)

    assert poll(OnESPollParams())
    calls = poll_attachments.bridge.get_upload_targets.call_args_list
    assert [len(call.args[0]) for call in calls] == [
        min(20, count - start) for start in range(0, count, 20)
    ]
    assert len(set(poll_attachments.issued)) == count
    assert outcome(app).get_summary()["attachments_uploaded"] == count
    assert all(not path.exists() for path in poll_attachments.paths)


@pytest.mark.parametrize(
    "failure",
    ["reference", "reservation", "duplicate", "invalid_id", "tempdir", "write"],
)
def test_poll_attachment_preparation_failures_still_create_findings(
    direct_app, poll_attachments, respx_mock, mocker, failure
):
    from soar_sdk.decorators import _es_poll_attachments as module

    app = direct_app
    bridge = poll_attachments.bridge
    if failure == "reference":
        mocker.patch.object(
            sys.modules["es_poll_api"],
            "get_attachment_reference_base_url",
            side_effect=RuntimeError(TOKEN),
        )
    elif failure == "reservation":
        bridge.get_upload_targets.side_effect = RuntimeError(TOKEN)
    elif failure in {"duplicate", "invalid_id"}:
        reserve = bridge.get_upload_targets.side_effect

        def invalid(names, key):
            targets = reserve(names, key)
            targets[0]["attachment_id"] = (
                "invalid"
                if failure == "invalid_id"
                else "00000000-0000-0000-0000-000000000001"
            )
            return targets

        bridge.get_upload_targets.side_effect = invalid
    elif failure == "tempdir":
        mocker.patch.object(module, "TemporaryDirectory", side_effect=OSError(TOKEN))
    elif failure == "write":
        mocker.patch.object(module.Path, "write_bytes", side_effect=OSError(TOKEN))
    seen = []

    def create(request):
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"_time": "now", "finding_id": "created"})

    respx_mock.post(ENDPOINT).mock(side_effect=create)

    @app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        # The second reservation must not reuse the first chunk's IDs.
        yield attached_finding(
            names=("email.eml",) * (21 if failure == "duplicate" else 1)
        )

    assert poll(OnESPollParams())
    summary = outcome(app).get_summary()
    assert summary["created"] == 1
    assert summary["attachments_failed"] == 1
    assert summary["status"] == "partial"
    if failure != "duplicate":
        assert "attachments" not in seen[0]["email"]
        assert "raw_email_link" not in seen[0]["email"]
        bridge.associate_subject_attachments.assert_not_called()
    assert TOKEN not in repr(vars(outcome(app)))
    assert all(not path.exists() for path in poll_attachments.paths)


@pytest.mark.parametrize(
    "route",
    [
        "https://other.example/attachment-proxy",
        "ftp://es.example:8089/path",
        URL + "/path?secret=value",
        URL + "/path#fragment",
        "https://user:password@es.example:8089/path",
        "not a url",
        123,
    ],
)
def test_reference_route_is_trusted_same_origin(direct_app, monkeypatch, route):
    from soar_sdk.decorators._es_poll_attachments import _reference_base_url

    monkeypatch.setattr(
        sys.modules["es_poll_api"],
        "get_attachment_reference_base_url",
        lambda: route,
        raising=False,
    )
    with pytest.raises(ValueError, match="route is unavailable") as caught:
        _reference_base_url(URL)
    assert caught.value.__context__ is None


def test_poll_splits_finding_batches_before_attachment_limit(
    direct_app, poll_attachments, respx_mock
):
    from uuid import UUID

    seen = []

    def create(request):
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"_time": "now", "finding_id": str(len(seen))})

    respx_mock.post(ENDPOINT).mock(side_effect=create)

    @direct_app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        for index in range(26):
            yield attached_finding(str(index))

    assert poll(OnESPollParams())
    assert [
        len(call.args[0])
        for call in poll_attachments.bridge.get_upload_targets.call_args_list
    ] == [20, 6]
    assert [
        len(call.args[0])
        for call in poll_attachments.bridge.associate_subject_attachments.call_args_list
    ] == [20, 6]
    linked = [
        entry
        for call in poll_attachments.bridge.associate_subject_attachments.call_args_list
        for entry in call.args[0]
    ]
    assert linked == [
        {"subject_id": str(i + 1), "attachment_ids": [str(UUID(int=i + 1))]}
        for i in range(26)
    ]
    assert outcome(direct_app).get_summary()["created"] == 26


def test_poll_composes_upload_and_finding_http_transports(
    direct_app, poll_attachments, mocker, monkeypatch, caplog
):
    from http.client import HTTPConnection
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    from soar_sdk.apis import _attachment_upload as uploader

    # Keep reservation and queueing at the bundle boundary, but exercise both
    # actual HTTP bodies against a local server. TLS is covered by uploader tests.
    mocker.stop(poll_attachments.upload_mock)
    events = []
    payloads = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path.startswith("/upload"):
                assert TOKEN not in str(self.headers)
                assert b"private-file-contents" in body
                assert b"form-secret" in body
                events.append("upload")
                self.send_response(204)
                self.end_headers()
            else:
                assert events.count("upload") == 2
                assert self.headers["Authorization"] == "Bearer " + TOKEN
                events.append("create")
                payloads.append(json.loads(body))
                response = json.dumps(
                    {"_time": "now", "finding_id": f"created-{len(payloads)}"}
                ).encode()
                self.send_response(201)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        monkeypatch.setattr(
            sys.modules["es_poll_api"], "get_es_context", lambda: (base, TOKEN)
        )
        monkeypatch.setattr(
            sys.modules["es_poll_api"],
            "get_attachment_reference_base_url",
            lambda: base + "/attachment-proxy",
        )
        mocker.patch.object(
            uploader,
            "HTTPSConnection",
            side_effect=lambda *_args, **kwargs: HTTPConnection(
                "127.0.0.1", server.server_port, **kwargs
            ),
        )

        @direct_app.on_es_poll()
        def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
            yield attached_finding("first")
            yield attached_finding("second")

        try:
            assert poll(OnESPollParams())
        finally:
            server.shutdown()
            thread.join()
    assert events == ["upload", "upload", "create", "create"]
    poll_attachments.bridge.associate_subject_attachments.assert_called_once_with(
        [
            {"subject_id": f"created-{index + 1}", "attachment_ids": [identifier]}
            for index, identifier in enumerate(poll_attachments.issued)
        ]
    )
    assert outcome(direct_app).get_summary()["status"] == "success"
    rendered = repr(vars(outcome(direct_app))) + caplog.text
    for secret in (TOKEN, "private-file-contents", "signed-secret", "form-secret"):
        assert secret not in rendered


@pytest.mark.parametrize("first_write_fails", [False, True])
def test_poll_replaces_local_references_and_selects_last_successful_raw_email(
    direct_app, poll_attachments, respx_mock, mocker, first_write_fails
):
    from pathlib import Path

    from soar_sdk.models.finding import FindingEmail, FindingEmailAttachment

    finding = attached_finding(names=("first.eml", "second.eml"))
    finding.email = FindingEmail(
        body="body",
        raw_email_link="https://old.example/raw",
        attachments=[
            FindingEmailAttachment(filename="stale", url="https://old.example/file")
        ],
    )
    if first_write_fails:
        write = Path.write_bytes

        def fail_first(path, data):
            if path.name == "0":
                path.write_text("incomplete")
                raise OSError("private-file-contents")
            return write(path, data)

        mocker.patch.object(Path, "write_bytes", autospec=True, side_effect=fail_first)
    route = respx_mock.post(ENDPOINT).respond(
        201, json={"_time": "now", "finding_id": "created"}
    )

    @direct_app.on_es_poll()
    def poll(params: OnESPollParams) -> Generator[Finding, int | None]:
        yield finding

    assert poll(OnESPollParams())
    email = json.loads(route.calls[0].request.content)["email"]
    assert email["body"] == "body"
    assert email["raw_email_link"].endswith(
        "attachment_id=" + poll_attachments.issued[1]
    )
    assert [item["filename"] for item in email["attachments"]] == (
        ["second.eml"] if first_write_fails else ["first.eml", "second.eml"]
    )
    assert finding.email.raw_email_link == "https://old.example/raw"
    assert finding.email.attachments[0].filename == "stale"
    assert all(not path.exists() for path in poll_attachments.paths)
    assert outcome(direct_app).get_summary()["attachments_failed"] == int(
        first_write_fails
    )
