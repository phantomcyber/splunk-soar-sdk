import io
import logging
import traceback
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from soar_sdk.apis import _attachment_upload as uploader
from soar_sdk.apis.attachments import Attachments
from soar_sdk.exceptions import ActionFailure, AttachmentUploadError
from soar_sdk.models import AttachmentUploadResult, AttachmentUploadTarget


@pytest.fixture
def target():
    return AttachmentUploadTarget(
        attachment_id="attachment-1",
        file_name="email.eml",
        upload_url="https://uploads.example/secret-path?signature=url-secret",
        form_fields=[
            {"name": "key", "value": "object-key"},
            {"name": "metadata", "value": "first"},
            {"name": "metadata", "value": "second"},
            {"name": "x-amz-security-token", "value": "form-secret"},
        ],
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        max_size_bytes=1024 * 1024,
    )


@pytest.fixture
def file(tmp_path):
    path = tmp_path / "download.tmp"
    path.write_bytes(b"file-secret\x00\xff\r\n" * 10000)
    return path


@pytest.fixture
def connection(mocker):
    connection = Mock()
    connection.getresponse.return_value.status = 204
    mocker.patch.object(uploader, "HTTPSConnection", return_value=connection)
    return connection


@pytest.mark.parametrize("status", [200, 201, 204])
def test_upload_over_http(file, target, status, caplog, capsys):
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append(
                (
                    self.path,
                    self.headers,
                    self.rfile.read(int(self.headers["Content-Length"])),
                )
            )
            self.send_response(status)
            self.end_headers()

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            target.upload_url = SecretStr(
                f"http://127.0.0.1:{server.server_port}/secret-path?signature=url-secret"
            )
            caplog.set_level(logging.DEBUG)
            result = Attachments().upload_file(str(file), target)
        finally:
            server.shutdown()
            thread.join()
    assert result == AttachmentUploadResult(
        attachment_id=target.attachment_id,
        file_name=target.file_name,
        size_bytes=file.stat().st_size,
    )
    assert file.exists()
    path, headers, body = captured[0]
    assert path == "/secret-path?signature=url-secret"
    assert "Transfer-Encoding" not in headers
    assert "Authorization" not in headers
    assert "Cookie" not in headers
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {headers['Content-Type']}\r\n\r\n".encode() + body
    )
    parts = list(message.iter_parts())
    assert [part.get_param("name", header="content-disposition") for part in parts] == [
        "key",
        "metadata",
        "metadata",
        "x-amz-security-token",
        "file",
    ]
    assert [part.get_payload(decode=True) for part in parts[:-1]] == [
        b"object-key",
        b"first",
        b"second",
        b"form-secret",
    ]
    assert parts[-1].get_filename() == "email.eml"
    assert parts[-1].get_payload(decode=True) == file.read_bytes()
    output = (
        caplog.text + str(capsys.readouterr()) + repr(result) + result.model_dump_json()
    )
    for secret in ("url-secret", "form-secret", "file-secret", "secret-path"):
        assert secret not in output


@pytest.mark.parametrize(
    "status, code",
    [
        (400, "rejected"),
        (401, "authorization"),
        (403, "authorization"),
        (500, "unavailable"),
        (503, "unavailable"),
        (301, "response"),
        (202, "response"),
    ],
)
def test_status_errors(file, target, connection, status, code):
    connection.getresponse.return_value.status = status
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target)
    assert caught.value.error_code == code
    assert caught.value.status_code == status
    assert caught.value.attachment_id == target.attachment_id
    connection.request.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("url-secret"), "timeout"),
        (OSError("form-secret"), "unavailable"),
        (HTTPException("file-secret"), "unavailable"),
        (ValueError("url-secret"), "unavailable"),
    ],
)
def test_transport_errors_are_sanitized(file, target, connection, error, code, caplog):
    connection.request.side_effect = error
    caplog.set_level(logging.DEBUG)
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target, timeout=0.1)
    assert caught.value.error_code == code
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    rendered = (
        "".join(traceback.format_exception(caught.value))
        + caplog.text
        + repr(vars(caught.value))
    )
    for secret in ("url-secret", "form-secret", "file-secret"):
        assert secret not in rendered
    connection.request.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "timeout", [0, -1, float("nan"), float("inf"), True, None, "secret"]
)
def test_invalid_timeout(file, target, connection, timeout):
    with pytest.raises(
        AttachmentUploadError, match="Invalid attachment upload inputs"
    ) as caught:
        Attachments().upload_file(file, target, timeout=timeout)
    assert caught.value.error_code == "validation"
    connection.request.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://uploads.example/file",
        "/relative",
        "https:///file",
        "https://user:secret@uploads.example/file",
        "https://uploads.example/file#secret",
        "https://uploads.example:invalid/file",
        "https://uploads.example/é",
    ],
)
def test_invalid_url(file, target, connection, url):
    target.upload_url = SecretStr(url)
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target)
    assert caught.value.error_code == "validation"
    connection.request.assert_not_called()


@pytest.mark.parametrize("name", ["file", "bad\rname", "bad\nname"])
def test_invalid_form_name(file, target, connection, name):
    target.form_fields[0].name = name
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target)
    assert caught.value.error_code == "validation"
    connection.request.assert_not_called()


def test_invalid_target(file, connection):
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, {"upload_url": "url-secret"})
    assert caught.value.attachment_id is None
    assert caught.value.error_code == "validation"


@pytest.mark.parametrize(
    "change, code",
    [
        ("expired", "expired"),
        ("oversize", "validation"),
        ("missing", "file"),
        ("directory", "file"),
        ("invalid_path", "validation"),
        ("filename", "validation"),
    ],
)
def test_preflight(file, target, connection, change, code):
    if change == "expired":
        target.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif change == "oversize":
        target.max_size_bytes = 1
    elif change == "missing":
        file.unlink()
    elif change == "directory":
        file = file.parent
    elif change == "invalid_path":
        file = None
    else:
        target.file_name = "bad\nname"
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target)
    assert caught.value.error_code == code
    connection.request.assert_not_called()


def test_streams_and_closes_file(file, target, connection):
    def send(*_args, body, **_kwargs):
        chunks = list(body)
        assert b"".join(chunks[1:-1]) == file.read_bytes()
        assert all(len(chunk) <= 64 * 1024 for chunk in chunks[1:-1])

    connection.request.side_effect = send
    result = Attachments().upload_file(file, target, timeout=12)
    assert result.size_bytes == file.stat().st_size
    uploader.HTTPSConnection.assert_called_once_with(
        "uploads.example", None, timeout=12
    )
    connection.set_debuglevel.assert_called_once_with(0)


@pytest.mark.parametrize("actual, expected", [(b"", 0), (b"a", 2), (b"ab", 1)])
def test_changed_file(actual, expected):
    body = uploader._body(io.BytesIO(actual), expected, b"prefix", b"suffix")
    if actual:
        with pytest.raises(OSError, match="changed during upload"):
            list(body)
    else:
        assert list(body) == [b"prefix", b"suffix"]


def test_per_file_results_keep_identity(file, target, connection):
    connection.getresponse.side_effect = [Mock(status=403), Mock(status=204)]
    outcomes = []
    for attachment_id in ("attachment-failed", "attachment-success"):
        current = target.model_copy(update={"attachment_id": attachment_id})
        try:
            outcomes.append(Attachments().upload_file(file, current))
        except AttachmentUploadError as error:
            outcomes.append(error)
    assert [outcome.attachment_id for outcome in outcomes] == [
        "attachment-failed",
        "attachment-success",
    ]
    assert isinstance(outcomes[1], AttachmentUploadResult)


def test_close_error_does_not_leak(file, target, connection):
    connection.close.side_effect = OSError("url-secret")
    assert Attachments().upload_file(file, target).attachment_id == target.attachment_id


def test_timeout_overflow(file, target, connection):
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target, timeout=10**1000)
    assert caught.value.error_code == "validation"
    assert caught.value.__context__ is None
    connection.request.assert_not_called()


def test_bulk_reservation_uploads_and_links_keep_mapping(file, target, connection):
    targets = [
        target.model_copy(update={"attachment_id": f"attachment-{number}"})
        for number in range(3)
    ]
    bridge = Mock()
    bridge.get_upload_targets.return_value = [item.model_dump() for item in targets]
    bridge.associate_subject_attachments.return_value = "message-1"
    attachments = Attachments(bridge)
    reserved = attachments.get_upload_targets(["email.eml"] * 3, "batch-id")
    uploaded = [attachments.upload_file(file, item) for item in reserved]
    associations = [
        {
            "subject_id": "finding-first",
            "attachment_ids": [item.attachment_id for item in uploaded[:2]],
        },
        {"subject_id": "finding-second", "attachment_ids": [uploaded[2].attachment_id]},
    ]
    assert attachments.associate_subject_attachments(associations) == "message-1"
    bridge.get_upload_targets.assert_called_once_with(["email.eml"] * 3, "batch-id")
    bridge.associate_subject_attachments.assert_called_once_with(
        [
            {
                "subject_id": "finding-first",
                "attachment_ids": ["attachment-0", "attachment-1"],
            },
            {"subject_id": "finding-second", "attachment_ids": ["attachment-2"]},
        ]
    )
    assert connection.request.call_count == 3


def test_named_pipe_is_rejected_before_open(tmp_path, target, connection, mocker):
    import os

    pipe = tmp_path / "attachment.pipe"
    os.mkfifo(pipe)
    opened = mocker.patch.object(uploader.Path, "open")
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(pipe, target)
    assert caught.value.error_code == "file"
    opened.assert_not_called()
    connection.request.assert_not_called()


@pytest.mark.parametrize("status", [204, 403])
def test_file_is_closed_after_upload(file, target, connection, mocker, status):
    handle = file.open("rb")
    mocker.patch.object(uploader.Path, "open", return_value=handle)
    connection.getresponse.return_value.status = status
    if status == 204:
        Attachments().upload_file(file, target)
    else:
        with pytest.raises(AttachmentUploadError):
            Attachments().upload_file(file, target)
    assert handle.closed
    assert file.exists()


def test_open_failure_is_sanitized(file, target, connection, mocker):
    mocker.patch.object(
        uploader.Path, "open", side_effect=PermissionError("file-secret")
    )
    with pytest.raises(AttachmentUploadError) as caught:
        Attachments().upload_file(file, target)
    assert caught.value.error_code == "file"
    assert caught.value.__context__ is None
    assert "file-secret" not in "".join(traceback.format_exception(caught.value))
    connection.request.assert_not_called()


def test_https_rejects_untrusted_certificate(tmp_path, file, target):
    import ssl

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    certificate_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    certificate_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate_file, key_file)
    with HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            target.upload_url = SecretStr(
                f"https://localhost:{server.server_port}/secret-path?signature=url-secret"
            )
            with pytest.raises(AttachmentUploadError) as caught:
                Attachments().upload_file(file, target, timeout=2)
        finally:
            server.shutdown()
            thread.join()
    assert caught.value.error_code == "unavailable"
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert caught.value.status_code is None
    assert "url-secret" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    "workers, expected, count", [(None, 4, 8), (1, 1, 2), (2, 2, 4), (1000, 2, 2)]
)
def test_batch_concurrency_is_bounded_and_results_are_ordered(
    file, target, mocker, workers, expected, count
):
    from threading import Barrier, Lock

    api = Attachments()
    barrier = Barrier(expected, timeout=5)
    lock = Lock()
    active = maximum = 0

    def upload(path, current, *, timeout):
        nonlocal active, maximum
        assert path == file
        assert timeout == (30.0 if workers is None else 1.5)
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait()
        with lock:
            active -= 1
        return AttachmentUploadResult(
            attachment_id=current.attachment_id,
            file_name=current.file_name,
            size_bytes=0,
        )

    mocker.patch.object(api, "upload_file", side_effect=upload)
    jobs = [
        (file, target.model_copy(update={"attachment_id": f"attachment-{i}"}))
        for i in range(count)
    ]
    kwargs = {} if workers is None else {"max_workers": workers, "timeout": 1.5}
    outcomes = api.upload_files(jobs, **kwargs)
    assert maximum == expected
    assert active == 0
    assert [item.attachment_id for item in outcomes] == [
        f"attachment-{i}" for i in range(count)
    ]
    assert all(item.success and item.size_bytes == 0 for item in outcomes)


@pytest.mark.parametrize("workers", [0, -1, True, None, 1.5, "4"])
def test_batch_rejects_invalid_worker_count(workers):
    with pytest.raises(ActionFailure, match="positive integer"):
        Attachments().upload_files([], max_workers=workers)


@pytest.mark.parametrize(
    "shape",
    [
        None,
        "url-secret",
        [()],
        [("file",)],
        [("file", "url-secret")],
        [(None, "url-secret")],
        [("file", "url-secret", "extra")],
    ],
)
def test_batch_rejects_invalid_pairs_without_leaking_inputs(shape, mocker):
    api = Attachments()
    upload = mocker.patch.object(api, "upload_file")
    with pytest.raises(ActionFailure) as caught:
        api.upload_files(shape)
    assert "url-secret" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None
    upload.assert_not_called()


def test_batch_rejects_reused_attachment_id(file, target, mocker):
    api = Attachments()
    upload = mocker.patch.object(api, "upload_file")
    with pytest.raises(ActionFailure, match="distinct attachment IDs"):
        api.upload_files([(file, target), (file, target)])
    upload.assert_not_called()


def test_batch_empty_and_invalid_upload_do_not_use_bridge(file, target, connection):
    api = Attachments(bridge=Mock(side_effect=AssertionError("bridge called")))
    assert api.upload_files([]) == []
    outcome = api.upload_files([(file, target)], timeout=0)[0]
    assert not outcome.success
    assert outcome.attachment_id == target.attachment_id
    assert outcome.error_code == "validation"
    assert outcome.status_code is None
    connection.request.assert_not_called()
    uploaded = api.upload_files([(file, target)])[0]
    assert uploaded.model_dump(exclude_none=True) == {
        "attachment_id": target.attachment_id,
        "file_name": target.file_name,
        "success": True,
        "size_bytes": file.stat().st_size,
    }
    connection.request.assert_called_once()


def test_parallel_http_upload_failure_does_not_stop_other_files(
    file, target, caplog, capsys
):
    from http.server import ThreadingHTTPServer
    from threading import Barrier

    barrier = Barrier(2, timeout=5)
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            barrier.wait()
            self.send_response(403 if self.path.startswith("/failed") else 204)
            self.end_headers()
            if self.path.startswith("/failed"):
                self.wfile.write(b"form-secret")

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            jobs = [
                (
                    file,
                    target.model_copy(
                        update={
                            "attachment_id": name,
                            "upload_url": SecretStr(
                                f"http://127.0.0.1:{server.server_port}/{name}?signature=url-secret"
                            ),
                        }
                    ),
                )
                for name in ("failed", "success")
            ]
            caplog.set_level(logging.DEBUG)
            outcomes = Attachments().upload_files(jobs, max_workers=2, timeout=2)
        finally:
            server.shutdown()
            thread.join()
    assert [item.attachment_id for item in outcomes] == ["failed", "success"]
    assert [item.success for item in outcomes] == [False, True]
    assert outcomes[0].error_code == "authorization"
    assert outcomes[0].status_code == 403
    assert outcomes[1].size_bytes == file.stat().st_size
    assert len(received) == 2
    assert all(file.read_bytes() in body for body in received)
    rendered = (
        repr(outcomes)
        + "".join(item.model_dump_json() for item in outcomes)
        + caplog.text
        + str(capsys.readouterr())
    )
    assert file.exists()
    for secret in ("url-secret", "form-secret", "file-secret"):
        assert secret not in rendered


def test_parallel_completion_order_does_not_change_attachment_mapping(
    file, target, mocker
):
    from threading import Event

    api = Attachments()
    second_completed = Event()
    completed = []

    def upload(path, current, *, timeout):
        if current.attachment_id == "first":
            assert second_completed.wait(timeout=5)
            completed.append("first")
        else:
            completed.append("second")
            second_completed.set()
        return AttachmentUploadResult(
            attachment_id=current.attachment_id,
            file_name=current.file_name,
            size_bytes=0,
        )

    mocker.patch.object(api, "upload_file", side_effect=upload)
    outcomes = api.upload_files(
        [
            (file, target.model_copy(update={"attachment_id": name}))
            for name in ("first", "second")
        ],
        max_workers=2,
    )
    assert completed == ["second", "first"]
    assert [item.attachment_id for item in outcomes] == ["first", "second"]
    assert all(item.success for item in outcomes)


def test_queued_target_expiry_is_checked_before_its_upload(file, target, connection):
    queued = target.model_copy(update={"attachment_id": "queued"})

    def expire_queued_target(*_args, **_kwargs):
        queued.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    connection.request.side_effect = expire_queued_target
    outcomes = Attachments().upload_files(
        [(file, target), (file, queued)], max_workers=1
    )
    assert [item.attachment_id for item in outcomes] == [target.attachment_id, "queued"]
    assert [item.success for item in outcomes] == [True, False]
    assert outcomes[1].error_code == "expired"
    assert outcomes[1].status_code is None
    connection.request.assert_called_once()
