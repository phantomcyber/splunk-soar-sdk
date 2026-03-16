import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from soar_sdk.extras.email.base import (
    EmailAttachment,
    EmailBody,
    EmailData,
    EmailHeaders,
    _is_msg_bytes,
    extract_email_data,
)
from soar_sdk.extras.email.outlook import (
    OutlookEmailData,
    _extract_outlook_attachments,
    _extract_outlook_body,
    _extract_outlook_headers,
    _extract_outlook_urls,
    extract_outlook_email_data,
)
from soar_sdk.extras.email.rfc5322 import RFC5322EmailData

# OLE2 magic bytes prefix for .msg files
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"

SIMPLE_EML = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Thu, 01 Jan 2024 12:00:00 +0000
Message-ID: <test123@example.com>

This is a plain text body.
"""


def _mock_msg(
    sender: str = "sender@example.com",
    to: str = "recipient@example.com",
    cc: str = "cc@example.com",
    bcc: str | None = None,
    subject: str = "Test Outlook Subject",
    date: str = "Thu, 01 Jan 2024 12:00:00 +0000",
    message_id: str = "<outlook123@example.com>",
    body: object = "Plain text body with https://example.com/link",
    html_body: object = '<html><body><a href="https://html.example.com">link</a></body></html>',
    header_dict: dict[str, object] | str | None = "DEFAULT",
    attachments: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock extract_msg Message object."""
    msg = MagicMock()
    msg.sender = sender
    msg.to = to
    msg.cc = cc
    msg.bcc = bcc
    msg.subject = subject
    msg.date = date
    msg.messageId = message_id
    msg.body = body
    msg.htmlBody = html_body
    if header_dict == "DEFAULT":
        msg.headerDict = {
            "X-Mailer": "Outlook 16.0",
            "X-Priority": "1",
            "Reply-To": "reply@example.com",
            "Content-Type": "multipart/mixed",
            "From": "sender@example.com",
        }
    else:
        msg.headerDict = header_dict
    msg.attachments = attachments if attachments is not None else []
    msg.close = MagicMock()
    return msg


def _mock_attachment(
    name: str | None = "document.pdf",
    mimetype: str = "application/pdf",
    data: bytes | str | None = b"fake pdf content",
    cid: str | None = None,
) -> MagicMock:
    """Create a mock extract_msg Attachment object."""
    att = MagicMock()
    att.name = name
    att.mimetype = mimetype
    att.data = data
    att.cid = cid
    return att


# --- Tests for _is_msg_bytes ---


def test_is_msg_bytes_with_ole2_magic() -> None:
    assert _is_msg_bytes(OLE2_MAGIC + b"rest of file") is True


def test_is_msg_bytes_with_non_ole2() -> None:
    assert _is_msg_bytes(b"From: sender@example.com") is False


def test_is_msg_bytes_with_empty() -> None:
    assert _is_msg_bytes(b"") is False


def test_is_msg_bytes_with_short_bytes() -> None:
    assert _is_msg_bytes(b"\xd0\xcf") is False


# --- Tests for _extract_outlook_headers ---


def test_extract_outlook_headers_basic() -> None:
    msg = _mock_msg()
    headers = _extract_outlook_headers(msg, email_id="test-id")

    assert headers.email_id == "test-id"
    assert headers.message_id == "<outlook123@example.com>"
    assert headers.to == "recipient@example.com"
    assert headers.from_address == "sender@example.com"
    assert headers.subject == "Test Outlook Subject"
    assert headers.date == "Thu, 01 Jan 2024 12:00:00 +0000"
    assert headers.cc == "cc@example.com"
    assert headers.bcc is None
    assert headers.x_mailer == "Outlook 16.0"
    assert headers.x_priority == "1"
    assert headers.reply_to == "reply@example.com"
    assert headers.content_type == "multipart/mixed"


def test_extract_outlook_headers_no_email_id() -> None:
    msg = _mock_msg()
    headers = _extract_outlook_headers(msg)
    assert headers.email_id is None


def test_extract_outlook_headers_empty_header_dict() -> None:
    msg = _mock_msg(header_dict={})
    headers = _extract_outlook_headers(msg)

    assert headers.x_mailer is None
    assert headers.x_priority is None
    assert headers.reply_to is None
    assert headers.content_type is None
    assert headers.received == []


def test_extract_outlook_headers_none_header_dict() -> None:
    msg = _mock_msg()
    msg.headerDict = None
    headers = _extract_outlook_headers(msg)

    assert headers.x_mailer is None
    assert headers.received == []


def test_extract_outlook_headers_received_as_list() -> None:
    msg = _mock_msg(
        header_dict={
            "Received": ["from server1.example.com", "from server2.example.com"],
        }
    )
    headers = _extract_outlook_headers(msg)

    assert len(headers.received) == 2
    assert "server1.example.com" in headers.received[0]


def test_extract_outlook_headers_received_as_string() -> None:
    msg = _mock_msg(
        header_dict={
            "Received": "from server1.example.com",
        }
    )
    headers = _extract_outlook_headers(msg)

    assert len(headers.received) == 1
    assert "server1.example.com" in headers.received[0]


def test_extract_outlook_headers_raw_headers_populated() -> None:
    msg = _mock_msg(
        header_dict={
            "X-Custom-Header": "custom_value",
            "Received": ["from server1"],
        }
    )
    headers = _extract_outlook_headers(msg)

    assert "X-Custom-Header" in headers.raw_headers
    assert headers.raw_headers["X-Custom-Header"] == "custom_value"
    assert "Received" not in headers.raw_headers


def test_extract_outlook_headers_raw_headers_none_value() -> None:
    msg = _mock_msg(
        header_dict={
            "X-Null": None,
        }
    )
    headers = _extract_outlook_headers(msg)
    assert headers.raw_headers["X-Null"] is None


def test_extract_outlook_headers_non_string_x_mailer() -> None:
    """Non-string values for X-Mailer etc. should be treated as None."""
    msg = _mock_msg(
        header_dict={
            "X-Mailer": 12345,
            "X-Priority": ["not", "a", "string"],
            "Reply-To": 42,
            "Content-Type": True,
        }
    )
    headers = _extract_outlook_headers(msg)

    assert headers.x_mailer is None
    assert headers.x_priority is None
    assert headers.reply_to is None
    assert headers.content_type is None


# --- Tests for _extract_outlook_body ---


def test_extract_outlook_body_plain_and_html() -> None:
    msg = _mock_msg()
    body = _extract_outlook_body(msg)

    assert body.plain_text is not None
    assert "Plain text body" in body.plain_text
    assert body.html is not None
    assert "html.example.com" in body.html


def test_extract_outlook_body_html_as_bytes() -> None:
    msg = _mock_msg(html_body=b"<html><body>Bytes HTML</body></html>")
    body = _extract_outlook_body(msg)

    assert body.html is not None
    assert "Bytes HTML" in body.html


def test_extract_outlook_body_no_body() -> None:
    msg = _mock_msg(body=None, html_body=None)
    body = _extract_outlook_body(msg)

    assert body.plain_text is None
    assert body.html is None


def test_extract_outlook_body_empty_string() -> None:
    msg = _mock_msg(body="", html_body="")
    body = _extract_outlook_body(msg)

    assert body.plain_text is None
    assert body.html is None


def test_extract_outlook_body_non_string_body() -> None:
    msg = _mock_msg(body=12345, html_body=12345)
    body = _extract_outlook_body(msg)

    assert body.plain_text is None
    assert body.html is None


# --- Tests for _extract_outlook_urls ---


def test_extract_outlook_urls() -> None:
    msg = _mock_msg()
    urls = _extract_outlook_urls(msg)

    assert "https://example.com/link" in urls
    assert "https://html.example.com" in urls


def test_extract_outlook_urls_no_body() -> None:
    msg = _mock_msg(body=None, html_body=None)
    urls = _extract_outlook_urls(msg)

    assert urls == []


# --- Tests for _extract_outlook_attachments ---


def test_extract_outlook_attachments_basic() -> None:
    att = _mock_attachment()
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg)

    assert len(attachments) == 1
    assert attachments[0].filename == "document.pdf"
    assert attachments[0].content_type == "application/pdf"
    assert attachments[0].size == len(b"fake pdf content")
    assert attachments[0].content is None
    assert attachments[0].is_inline is False


def test_extract_outlook_attachments_with_content() -> None:
    att = _mock_attachment()
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg, include_content=True)

    assert len(attachments) == 1
    assert attachments[0].content == b"fake pdf content"


def test_extract_outlook_attachments_inline() -> None:
    att = _mock_attachment(cid="<image001>")
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg)

    assert len(attachments) == 1
    assert attachments[0].is_inline is True
    assert attachments[0].content_id == "image001"


def test_extract_outlook_attachments_no_name() -> None:
    att = _mock_attachment(name=None)
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg)

    assert len(attachments) == 1
    assert attachments[0].filename == "unnamed_attachment"


def test_extract_outlook_attachments_non_bytes_data() -> None:
    att = _mock_attachment(data="not bytes")
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg)

    assert len(attachments) == 1
    assert attachments[0].size == 0
    assert attachments[0].content is None


def test_extract_outlook_attachments_empty() -> None:
    msg = _mock_msg(attachments=[])
    attachments = _extract_outlook_attachments(msg)

    assert len(attachments) == 0


def test_extract_outlook_attachments_no_cid_content() -> None:
    """Attachment with no cid and include_content=True but no data."""
    att = _mock_attachment(data=None, cid=None)
    msg = _mock_msg(attachments=[att])
    attachments = _extract_outlook_attachments(msg, include_content=True)

    assert len(attachments) == 1
    assert attachments[0].content is None
    assert attachments[0].content_id is None
    assert attachments[0].is_inline is False


# --- Tests for extract_outlook_email_data ---


@patch("extract_msg.openMsg")
def test_extract_outlook_email_data_basic(mock_open_msg: MagicMock) -> None:
    msg = _mock_msg()
    mock_open_msg.return_value = msg

    result = extract_outlook_email_data(
        OLE2_MAGIC + b"fake msg data", email_id="outlook-test"
    )

    assert isinstance(result, OutlookEmailData)
    assert result.headers.email_id == "outlook-test"
    assert result.headers.subject == "Test Outlook Subject"
    assert result.body.plain_text is not None
    assert len(result.urls) > 0
    msg.close.assert_called_once()


@patch("extract_msg.openMsg")
def test_extract_outlook_email_data_closes_on_exception(
    mock_open_msg: MagicMock,
) -> None:
    """Ensure msg.close() is called even if extraction raises."""
    msg = _mock_msg()
    mock_open_msg.return_value = msg

    result = extract_outlook_email_data(OLE2_MAGIC + b"data")
    msg.close.assert_called_once()
    assert isinstance(result, OutlookEmailData)


# --- Tests for EmailData base class ---


def test_email_data_to_dict_with_str() -> None:
    data = EmailData(
        raw_email="raw text",
        headers=EmailHeaders(email_id="test"),
        body=EmailBody(plain_text="hello"),
    )
    d = data.to_dict()
    assert d["raw_email"] == "raw text"
    assert d["headers"]["email_id"] == "test"
    assert d["body"]["plain_text"] == "hello"


def test_email_data_to_dict_with_bytes() -> None:
    raw = b"\xd0\xcf\x11\xe0binary"
    data = EmailData(
        raw_email=raw,
        headers=EmailHeaders(),
        body=EmailBody(),
    )
    d = data.to_dict()
    assert isinstance(d["raw_email"], str)
    assert d["raw_email"] == base64.b64encode(raw).decode("ascii")


def test_email_data_to_dict_attachments() -> None:
    att = EmailAttachment(
        filename="test.pdf",
        content_type="application/pdf",
        size=100,
        content_id="cid1",
        is_inline=True,
    )
    data = EmailData(
        raw_email="raw",
        headers=EmailHeaders(),
        body=EmailBody(),
        attachments=[att],
    )
    d = data.to_dict()
    assert len(d["attachments"]) == 1
    assert d["attachments"][0]["filename"] == "test.pdf"
    assert d["attachments"][0]["is_inline"] is True


def test_email_data_to_dict_urls() -> None:
    data = EmailData(
        raw_email="raw",
        headers=EmailHeaders(),
        body=EmailBody(),
        urls=["https://example.com"],
    )
    d = data.to_dict()
    assert d["urls"] == ["https://example.com"]


def test_email_data_to_dict_all_header_fields() -> None:
    headers = EmailHeaders(
        email_id="id1",
        message_id="<msg1>",
        to="to@example.com",
        from_address="from@example.com",
        subject="Subject",
        date="Thu, 01 Jan 2024",
        received=["from server1"],
        cc="cc@example.com",
        bcc="bcc@example.com",
        x_mailer="Mailer",
        x_priority="1",
        reply_to="reply@example.com",
        content_type="text/plain",
        raw_headers={"X-Custom": "val"},
    )
    data = EmailData(
        raw_email="raw",
        headers=headers,
        body=EmailBody(),
    )
    d = data.to_dict()
    assert d["headers"]["from"] == "from@example.com"
    assert d["headers"]["received"] == ["from server1"]
    assert d["headers"]["raw_headers"] == {"X-Custom": "val"}


# --- Tests for class hierarchy ---


def test_outlook_email_data_is_email_data() -> None:
    assert OutlookEmailData is EmailData


def test_rfc5322_email_data_is_email_data() -> None:
    assert RFC5322EmailData is EmailData


# --- Tests for extract_email_data auto-detection ---


def test_extract_email_data_with_eml_string() -> None:
    result = extract_email_data(SIMPLE_EML, email_id="eml-str")
    assert isinstance(result, RFC5322EmailData)
    assert result.headers.email_id == "eml-str"
    assert result.headers.subject == "Test Subject"


def test_extract_email_data_with_eml_bytes() -> None:
    result = extract_email_data(SIMPLE_EML.encode("utf-8"), email_id="eml-bytes")
    assert isinstance(result, RFC5322EmailData)
    assert result.headers.subject == "Test Subject"


@patch("soar_sdk.extras.email.outlook.extract_outlook_email_data")
def test_extract_email_data_with_msg_bytes(mock_extract: MagicMock) -> None:
    mock_extract.return_value = OutlookEmailData(
        raw_email=OLE2_MAGIC + b"data",
        headers=EmailHeaders(subject="Outlook Subject"),
        body=EmailBody(),
    )
    result = extract_email_data(OLE2_MAGIC + b"data", email_id="msg-bytes")
    assert isinstance(result, OutlookEmailData)
    mock_extract.assert_called_once_with(OLE2_MAGIC + b"data", "msg-bytes", False)


def test_extract_email_data_with_eml_path(tmp_path: Path) -> None:
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(SIMPLE_EML)

    result = extract_email_data(eml_file, email_id="eml-path")
    assert isinstance(result, RFC5322EmailData)
    assert result.headers.subject == "Test Subject"


@patch("soar_sdk.extras.email.outlook.extract_outlook_email_data")
def test_extract_email_data_with_msg_path(
    mock_extract: MagicMock, tmp_path: Path
) -> None:
    msg_file = tmp_path / "test.msg"
    msg_file.write_bytes(OLE2_MAGIC + b"fake msg data")

    mock_extract.return_value = OutlookEmailData(
        raw_email=OLE2_MAGIC + b"fake msg data",
        headers=EmailHeaders(subject="Outlook Subject"),
        body=EmailBody(),
    )
    result = extract_email_data(msg_file, email_id="msg-path")
    assert isinstance(result, OutlookEmailData)
    mock_extract.assert_called_once()


def test_extract_email_data_with_str_eml_path(tmp_path: Path) -> None:
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(SIMPLE_EML)

    result = extract_email_data(str(eml_file), email_id="str-eml-path")
    assert isinstance(result, RFC5322EmailData)
    assert result.headers.subject == "Test Subject"


@patch("soar_sdk.extras.email.outlook.extract_outlook_email_data")
def test_extract_email_data_with_str_msg_path(
    mock_extract: MagicMock, tmp_path: Path
) -> None:
    msg_file = tmp_path / "test.msg"
    msg_file.write_bytes(OLE2_MAGIC + b"fake msg data")

    mock_extract.return_value = OutlookEmailData(
        raw_email=OLE2_MAGIC + b"fake msg data",
        headers=EmailHeaders(subject="Outlook Subject"),
        body=EmailBody(),
    )
    result = extract_email_data(str(msg_file), email_id="str-msg-path")
    assert isinstance(result, OutlookEmailData)


def test_extract_email_data_str_not_a_file() -> None:
    """String that looks like a path extension but doesn't exist is treated as raw text."""
    result = extract_email_data(SIMPLE_EML)
    assert isinstance(result, RFC5322EmailData)


def test_extract_email_data_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Unsupported email_input type"):
        extract_email_data(12345)  # type: ignore[arg-type]


def test_extract_email_data_unrecognized_extension(tmp_path: Path) -> None:
    bad_file = tmp_path / "test.xyz"
    bad_file.write_text("some content")

    with pytest.raises(ValueError, match="Unrecognized email file extension"):
        extract_email_data(bad_file)


def test_extract_email_data_eml_path_include_content(tmp_path: Path) -> None:
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(SIMPLE_EML)

    result = extract_email_data(eml_file, include_attachment_content=True)
    assert isinstance(result, RFC5322EmailData)
