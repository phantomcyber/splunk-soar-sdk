import sys
import traceback
from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from soar_sdk.apis.attachments import Attachments
from soar_sdk.exceptions import ActionFailure, AttachmentApiError

VALID_ASSOCIATIONS = [{"subject_id": "finding-1", "attachment_ids": ["attachment-1"]}]
SECRETS = ("upload-secret", "form-secret", "opaque-sensitive-value")


def assert_no_retained_secrets(error: BaseException) -> None:
    """Check where loggers and error reporters could read secrets from SDK code."""
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = [str(error), repr(error), *traceback.format_exception(error)]
    tb = error.__traceback__
    sdk_frames = 0
    while tb is not None:
        if tb.tb_frame.f_globals["__name__"].startswith("soar_sdk."):
            sdk_frames += 1
            rendered.extend(repr(value) for value in tb.tb_frame.f_locals.values())
        tb = tb.tb_next
    assert sdk_frames
    for secret in SECRETS:
        assert not any(secret in text for text in rendered)


@pytest.fixture
def upload_target_data():
    return {
        "attachment_id": "attachment-1",
        "file_name": "email.eml",
        "upload_url": "https://uploads.example/target?signature=upload-secret",
        "form_fields": [
            {"name": "key", "value": "object-key"},
            {"name": "x-amz-security-token", "value": "form-secret"},
            {"name": "metadata", "value": "first"},
            {"name": "metadata", "value": "second"},
        ],
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "max_size_bytes": 1024,
    }


@pytest.fixture
def attachment_bridge(monkeypatch, upload_target_data):
    bridge = SimpleNamespace(
        get_upload_targets=Mock(return_value=[upload_target_data]),
        associate_subject_attachments=Mock(return_value="dispatch-1"),
    )
    monkeypatch.setitem(sys.modules, "attachment_api", bridge)
    return bridge


@pytest.fixture
def attachments(app_with_action, attachment_bridge):
    return app_with_action.soar_client.attachments


def test_attachment_targets_map_to_multiple_findings(
    attachments, attachment_bridge, upload_target_data
):
    """Keep batch identities and multipart fields intact through association."""
    attachment_bridge.get_upload_targets.return_value = [
        upload_target_data,
        {**upload_target_data, "attachment_id": "attachment-2"},
        {
            **upload_target_data,
            "file_name": "evidence.pdf",
            "attachment_id": "attachment-3",
        },
    ]
    batch_id = "00000000-0000-4000-8000-000000000001"
    file_names = ["email.eml", "email.eml", "evidence.pdf"]

    targets = attachments.get_upload_targets(file_names, batch_id)
    message_id = attachments.associate_subject_attachments(
        [
            {
                "subject_id": "es:opaque-finding-1",
                "attachment_ids": [targets[0].attachment_id, targets[1].attachment_id],
            },
            {
                "subject_id": "es:opaque-finding-2",
                "attachment_ids": [targets[2].attachment_id],
            },
        ]
    )

    attachment_bridge.get_upload_targets.assert_called_once_with(file_names, batch_id)
    attachment_bridge.associate_subject_attachments.assert_called_once_with(
        [
            {
                "subject_id": "es:opaque-finding-1",
                "attachment_ids": ["attachment-1", "attachment-2"],
            },
            {
                "subject_id": "es:opaque-finding-2",
                "attachment_ids": ["attachment-3"],
            },
        ]
    )
    assert message_id == "dispatch-1"
    assert [target.file_name for target in targets] == file_names
    assert targets[0].upload_url.get_secret_value() == upload_target_data["upload_url"]
    assert [
        {"name": field.name, "value": field.value.get_secret_value()}
        for field in targets[0].form_fields
    ] == upload_target_data["form_fields"]
    assert targets[0].expires_at == datetime.fromisoformat(
        upload_target_data["expires_at"]
    )
    assert targets[0].max_size_bytes == 1024


def test_upload_target_credentials_are_masked(attachments):
    """Credentials never appear in repr or serialized output."""
    (target,) = attachments.get_upload_targets(["email.eml"], "batch-1")

    for rendered in (
        repr(target),
        str(target),
        str(target.model_dump()),
        target.model_dump_json(),
        *(repr(field) for field in target.form_fields),
    ):
        assert "upload-secret" not in rendered
        assert "form-secret" not in rendered


def test_injected_bridge_is_used_without_loading_runtime(
    monkeypatch, upload_target_data
):
    monkeypatch.setitem(sys.modules, "attachment_api", None)
    bridge = SimpleNamespace(
        get_upload_targets=Mock(return_value=[upload_target_data]),
        associate_subject_attachments=Mock(return_value="dispatch-1"),
    )
    api = Attachments(bridge=bridge)

    assert api.get_upload_targets(["email.eml"], "batch-1")[0].attachment_id == (
        "attachment-1"
    )
    assert api.associate_subject_attachments(VALID_ASSOCIATIONS) == "dispatch-1"


def test_file_name_sequences_are_accepted(attachments, attachment_bridge):
    targets = attachments.get_upload_targets(("email.eml",), "batch-1")

    assert [target.file_name for target in targets] == ["email.eml"]
    attachment_bridge.get_upload_targets.assert_called_once_with(
        ["email.eml"], "batch-1"
    )


@pytest.mark.parametrize(
    "file_names, idempotency_key",
    [
        ([], "batch-1"),
        ([""], "batch-1"),
        (["   "], "batch-1"),
        (["email.eml", "\t"], "batch-1"),
        ([123], "batch-1"),
        ("email.eml", "batch-1"),
        (["email.eml"], ""),
        (["email.eml"], "  "),
        (["email.eml"], None),
    ],
)
def test_invalid_target_requests_do_not_reach_runtime(
    attachments, attachment_bridge, file_names, idempotency_key
):
    with pytest.raises(ActionFailure, match="nonempty file names") as caught:
        attachments.get_upload_targets(file_names, idempotency_key)

    assert not isinstance(caught.value, AttachmentApiError)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    attachment_bridge.get_upload_targets.assert_not_called()


@pytest.mark.parametrize(
    "method_name, arguments",
    [
        ("get_upload_targets", (["email.eml"], "batch-1")),
        ("associate_subject_attachments", (VALID_ASSOCIATIONS,)),
    ],
)
def test_attachment_apis_require_runtime_bundle(
    app_with_action, monkeypatch, method_name, arguments
):
    monkeypatch.setitem(sys.modules, "attachment_api", None)
    operation = getattr(app_with_action.soar_client.attachments, method_name)

    with pytest.raises(
        AttachmentApiError, match="Lunar Base ingestion runtime"
    ) as caught:
        operation(*arguments)

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "error",
    [
        ModuleNotFoundError(
            "Missing runtime dependency: signature=upload-secret; token=form-secret",
            name="server_pb2_grpc",
        ),
        RuntimeError(
            "bridge initialization failed: signature=upload-secret; token=form-secret"
        ),
    ],
)
def test_broken_runtime_import_is_sanitized(app_with_action, monkeypatch, error):
    monkeypatch.setattr(
        "soar_sdk.apis.attachments.import_module", Mock(side_effect=error)
    )

    with pytest.raises(AttachmentApiError, match="failed to load") as caught:
        app_with_action.soar_client.attachments.get_upload_targets(
            ["email.eml"], "batch-1"
        )

    assert_no_retained_secrets(caught.value)
    assert caught.value.__suppress_context__
    rendered = "".join(traceback.format_exception(caught.value))
    assert "server_pb2_grpc" not in rendered


@pytest.mark.parametrize(
    "method_name, arguments, message",
    [
        ("get_upload_targets", (["email.eml"], "batch-1"), "record creation failed"),
        (
            "associate_subject_attachments",
            (VALID_ASSOCIATIONS,),
            "association failed",
        ),
    ],
)
@pytest.mark.parametrize(
    "error_type", [RuntimeError, ActionFailure, AttachmentApiError]
)
def test_runtime_failures_are_sanitized(
    attachments, attachment_bridge, method_name, arguments, message, error_type
):
    error = error_type(
        "StatusCode.UNAVAILABLE: https://uploads.example/?signature=upload-secret; "
        "token=form-secret; opaque-sensitive-value"
    )
    attachment_bridge.get_upload_targets.side_effect = error
    attachment_bridge.associate_subject_attachments.side_effect = error

    with pytest.raises(AttachmentApiError, match=message) as caught:
        getattr(attachments, method_name)(*arguments)

    assert_no_retained_secrets(caught.value)
    assert caught.value.__suppress_context__
    rendered = "".join(traceback.format_exception(caught.value))
    assert "StatusCode" not in rendered


@pytest.mark.parametrize(
    "invalid_targets",
    [
        None,
        [{}],
        [{"upload_url": "https://uploads.example/?signature=upload-secret"}],
        {"upload_url": "https://uploads.example/?signature=upload-secret"},
        "https://uploads.example/?signature=upload-secret",
    ],
    ids=["none", "empty", "partial", "not-a-list", "string"],
)
def test_invalid_upload_targets_are_reported_without_secrets(
    attachments, attachment_bridge, invalid_targets
):
    attachment_bridge.get_upload_targets.return_value = invalid_targets

    with pytest.raises(
        AttachmentApiError, match="Invalid attachment upload targets"
    ) as caught:
        attachments.get_upload_targets(["email.eml"], "batch-1")

    assert_no_retained_secrets(caught.value)


@pytest.mark.parametrize("mismatch", ["missing", "extra", "renamed", "reordered"])
def test_upload_targets_must_match_requested_files(
    attachments, attachment_bridge, upload_target_data, mismatch
):
    first = upload_target_data
    second = {**first, "file_name": "second.eml", "attachment_id": "attachment-2"}
    targets = {
        "missing": [first],
        "extra": [first, second, second],
        "renamed": [first, {**second, "file_name": "other.eml"}],
        "reordered": [second, first],
    }
    attachment_bridge.get_upload_targets.return_value = targets[mismatch]

    with pytest.raises(
        AttachmentApiError, match="do not match requested files"
    ) as caught:
        attachments.get_upload_targets(["email.eml", "second.eml"], "batch-1")

    assert_no_retained_secrets(caught.value)


@pytest.mark.parametrize(
    "file_names", [["email.eml", "evidence.pdf"], ["email.eml", "email.eml"]]
)
def test_upload_targets_reject_duplicate_attachment_ids(
    attachments, attachment_bridge, upload_target_data, file_names
):
    attachment_bridge.get_upload_targets.return_value = [
        {**upload_target_data, "file_name": name} for name in file_names
    ]

    with pytest.raises(AttachmentApiError, match="duplicate attachment IDs") as caught:
        attachments.get_upload_targets(file_names, "batch-1")

    assert_no_retained_secrets(caught.value)


def test_upload_target_matching_preserves_duplicate_filenames(
    attachments, attachment_bridge, upload_target_data
):
    attachment_bridge.get_upload_targets.return_value = [
        upload_target_data,
        {**upload_target_data, "attachment_id": "attachment-2"},
    ]

    targets = attachments.get_upload_targets(["email.eml", "email.eml"], "batch-1")

    assert [target.attachment_id for target in targets] == [
        "attachment-1",
        "attachment-2",
    ]


@pytest.mark.parametrize(
    "associations",
    [
        [],
        [{"subject_id": "", "attachment_ids": ["attachment-1"]}],
        [{"subject_id": "   ", "attachment_ids": ["attachment-1"]}],
        [{"subject_id": "finding-1", "attachment_ids": []}],
        [{"subject_id": "finding-1", "attachment_ids": [" "]}],
        [{"subject_id": "finding-1", "attachment_ids": [123]}],
        [{"subject_id": "finding-1"}],
        [{**VALID_ASSOCIATIONS[0], "attachment_id": "attachment-2"}],
    ],
)
def test_invalid_associations_do_not_reach_runtime(
    attachments, attachment_bridge, associations
):
    with pytest.raises(ActionFailure, match="association") as caught:
        attachments.associate_subject_attachments(associations)

    assert not isinstance(caught.value, AttachmentApiError)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    attachment_bridge.associate_subject_attachments.assert_not_called()


@pytest.mark.parametrize(
    "message_id",
    [None, "", "   ", 123, {"token": "form-secret"}],
)
def test_association_requires_a_message_id(attachments, attachment_bridge, message_id):
    attachment_bridge.associate_subject_attachments.return_value = message_id

    with pytest.raises(
        AttachmentApiError, match="invalid attachment association message ID"
    ) as caught:
        attachments.associate_subject_attachments(VALID_ASSOCIATIONS)

    assert_no_retained_secrets(caught.value)


def test_invalid_runtime_bridge_is_rejected(app_with_action, monkeypatch):
    monkeypatch.setitem(sys.modules, "attachment_api", SimpleNamespace())

    with pytest.raises(AttachmentApiError, match="runtime bridge is invalid"):
        app_with_action.soar_client.attachments.get_upload_targets(
            ["email.eml"], "batch-1"
        )


def test_attachment_api_error_formatting():
    error = AttachmentApiError("bridge failed")
    assert str(error) == "Attachment API error: bridge failed"

    error.set_action_name("on_es_poll")
    assert str(error) == "Attachment API error in on_es_poll: bridge failed"


def test_client_reuses_attachments_api(app_with_action):
    client = app_with_action.soar_client

    assert client.attachments is client.attachments


def test_runtime_bridge_is_loaded_once(monkeypatch, attachment_bridge):
    load = Mock(wraps=import_module)
    monkeypatch.setattr("soar_sdk.apis.attachments.import_module", load)
    api = Attachments()

    api.get_upload_targets(["email.eml"], "batch-1")
    api.associate_subject_attachments(VALID_ASSOCIATIONS)

    load.assert_called_once_with("attachment_api")


def test_target_validation_failures_do_not_retain_raw_targets(
    attachments, attachment_bridge, upload_target_data
):
    """Raw targets hold unmasked credentials and must not be reachable from frames."""
    attachment_bridge.get_upload_targets.return_value = [
        {**upload_target_data, "max_size_bytes": 0}
    ]

    with pytest.raises(
        AttachmentApiError, match="Invalid attachment upload targets"
    ) as caught:
        attachments.get_upload_targets(["email.eml"], "batch-1")

    assert_no_retained_secrets(caught.value)


@pytest.mark.parametrize(
    "upload_url",
    [
        "http://uploads.example/target?signature=upload-secret",
        "ftp://uploads.example/target?signature=upload-secret",
        "https:///target?signature=upload-secret",
        "/target?signature=upload-secret",
        "https://[upload-secret/target",
    ],
    ids=["http", "ftp", "no-host", "relative", "malformed"],
)
def test_upload_targets_require_https_urls(
    attachments, attachment_bridge, upload_target_data, upload_url
):
    attachment_bridge.get_upload_targets.return_value = [
        {**upload_target_data, "upload_url": upload_url}
    ]

    with pytest.raises(
        AttachmentApiError, match="Invalid attachment upload targets"
    ) as caught:
        attachments.get_upload_targets(["email.eml"], "batch-1")

    assert_no_retained_secrets(caught.value)


def test_upload_targets_require_form_fields(
    attachments, attachment_bridge, upload_target_data
):
    attachment_bridge.get_upload_targets.return_value = [
        {**upload_target_data, "form_fields": []}
    ]

    with pytest.raises(
        AttachmentApiError, match="Invalid attachment upload targets"
    ) as caught:
        attachments.get_upload_targets(["email.eml"], "batch-1")

    assert_no_retained_secrets(caught.value)
