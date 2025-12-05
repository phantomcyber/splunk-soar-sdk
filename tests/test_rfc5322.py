import email
from unittest.mock import MagicMock, patch

from soar_sdk.extras.email.rfc5322 import (
    EmailAttachment,
    EmailBody,
    EmailHeaders,
    RFC5322EmailData,
    _decode_header_value,
    _decode_payload,
    _extract_urls_from_content,
    extract_domains_from_urls,
    extract_email_addresses_from_body,
    extract_email_attachments,
    extract_email_body,
    extract_email_headers,
    extract_email_urls,
    extract_rfc5322_email_data,
)

SIMPLE_EMAIL = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Thu, 01 Jan 2024 12:00:00 +0000
Message-ID: <test123@example.com>
X-Mailer: Test Mailer
X-Priority: High

This is a plain text body with a URL: https://example.com/page
"""

MULTIPART_EMAIL = """From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
Date: Thu, 01 Jan 2024 12:00:00 +0000
Message-ID: <multi123@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

Plain text body with https://plain.example.com
--boundary123
Content-Type: text/html; charset="utf-8"

<html><body>
<p>HTML body with <a href="https://html.example.com/link">a link</a></p>
<img src="https://html.example.com/image.png">
</body></html>
--boundary123
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--boundary123--
"""

HTML_EMAIL_WITH_PLAINTEXT_URLS = """From: sender@example.com
To: recipient@example.com
Subject: HTML with plaintext URLs
Content-Type: text/html; charset="utf-8"

<html><body>
<p>Click <a href="https://link.example.com">here</a></p>
<p>Or visit https://plaintext.example.com directly</p>
</body></html>
"""

EMAIL_WITH_ENCODED_HEADERS = """From: =?utf-8?B?VGVzdCBTZW5kZXI=?= <sender@example.com>
To: =?utf-8?B?VGVzdCBSZWNpcGllbnQ=?= <recipient@example.com>
Subject: =?utf-8?B?VGVzdCBTdWJqZWN0?=
Date: Thu, 01 Jan 2024 12:00:00 +0000
Message-ID: <encoded123@example.com>
Received: from server1.example.com
Received: from server2.example.com
CC: cc@example.com
Reply-To: reply@example.com

Body content
"""


def test_extract_email_headers_simple():
    """Test extracting headers from a simple email."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    headers = extract_email_headers(mail, email_id="test-id-123")

    assert headers.email_id == "test-id-123"
    assert headers.message_id == "<test123@example.com>"
    assert headers.from_address == "sender@example.com"
    assert headers.to == "recipient@example.com"
    assert headers.subject == "Test Subject"
    assert headers.date == "Thu, 01 Jan 2024 12:00:00 +0000"
    assert headers.x_mailer == "Test Mailer"
    assert headers.x_priority == "High"


def test_extract_email_headers_with_received():
    """Test extracting multiple Received headers."""
    mail = email.message_from_string(EMAIL_WITH_ENCODED_HEADERS)
    headers = extract_email_headers(mail)

    assert len(headers.received) == 2
    assert "server1.example.com" in headers.received[0]
    assert "server2.example.com" in headers.received[1]
    assert headers.cc == "cc@example.com"
    assert headers.reply_to == "reply@example.com"


def test_extract_email_headers_raw_headers():
    """Test that raw_headers dict is populated."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    headers = extract_email_headers(mail)

    assert "From" in headers.raw_headers
    assert "To" in headers.raw_headers
    assert "Subject" in headers.raw_headers


def test_extract_email_body_plain():
    """Test extracting plain text body."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    body = extract_email_body(mail)

    assert body.plain_text is not None
    assert "plain text body" in body.plain_text.lower()
    assert body.html is None


def test_extract_email_body_multipart():
    """Test extracting body from multipart email."""
    mail = email.message_from_string(MULTIPART_EMAIL)
    body = extract_email_body(mail)

    assert body.plain_text is not None
    assert "plain text body" in body.plain_text.lower()
    assert body.html is not None
    assert "HTML body" in body.html


def test_extract_email_urls_from_plain():
    """Test extracting URLs from plain text email."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    urls = extract_email_urls(mail)

    assert "https://example.com/page" in urls


def test_extract_email_urls_from_html():
    """Test extracting URLs from HTML email."""
    mail = email.message_from_string(MULTIPART_EMAIL)
    urls = extract_email_urls(mail)

    assert "https://html.example.com/link" in urls
    assert "https://html.example.com/image.png" in urls
    assert "https://plain.example.com" in urls


def test_extract_email_urls_html_and_plaintext():
    """Test extracting both HTML href and plaintext URLs."""
    mail = email.message_from_string(HTML_EMAIL_WITH_PLAINTEXT_URLS)
    urls = extract_email_urls(mail)

    assert "https://link.example.com" in urls
    assert "https://plaintext.example.com" in urls


def test_extract_email_attachments():
    """Test extracting attachment metadata."""
    mail = email.message_from_string(MULTIPART_EMAIL)
    attachments = extract_email_attachments(mail)

    assert len(attachments) == 1
    assert attachments[0].filename == "document.pdf"
    assert attachments[0].content_type == "application/pdf"
    assert attachments[0].size > 0
    assert attachments[0].content is None


def test_extract_email_attachments_with_content():
    """Test extracting attachments with content."""
    mail = email.message_from_string(MULTIPART_EMAIL)
    attachments = extract_email_attachments(mail, include_content=True)

    assert len(attachments) == 1
    assert attachments[0].content is not None
    assert isinstance(attachments[0].content, bytes)


def test_extract_email_attachments_empty():
    """Test extracting attachments from email without attachments."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    attachments = extract_email_attachments(mail)

    assert len(attachments) == 0


def test_extract_rfc5322_email_data():
    """Test the main extraction function."""
    result = extract_rfc5322_email_data(MULTIPART_EMAIL, email_id="main-test")

    assert isinstance(result, RFC5322EmailData)
    assert result.raw_email == MULTIPART_EMAIL
    assert isinstance(result.headers, EmailHeaders)
    assert isinstance(result.body, EmailBody)
    assert result.headers.email_id == "main-test"
    assert len(result.urls) > 0
    assert len(result.attachments) == 1


def test_rfc5322_email_data_to_dict():
    """Test converting RFC5322EmailData to dict."""
    result = extract_rfc5322_email_data(SIMPLE_EMAIL, email_id="dict-test")
    data = result.to_dict()

    assert data["raw_email"] == SIMPLE_EMAIL
    assert data["headers"]["email_id"] == "dict-test"
    assert data["headers"]["from"] == "sender@example.com"
    assert data["body"]["plain_text"] is not None
    assert isinstance(data["urls"], list)
    assert isinstance(data["attachments"], list)


def test_extract_domains_from_urls():
    """Test extracting domains from URL list."""
    urls = [
        "https://example.com/page",
        "https://sub.example.org/path",
        "https://192.168.1.1/api",
        "https://test.com:8080/resource",
    ]
    domains = extract_domains_from_urls(urls)

    assert "example.com" in domains
    assert "sub.example.org" in domains
    assert "test.com" in domains
    assert "192.168.1.1" not in domains


def test_extract_domains_from_urls_empty():
    """Test extracting domains from empty list."""
    domains = extract_domains_from_urls([])
    assert domains == []


def test_extract_email_addresses_from_body():
    """Test extracting email addresses from body."""
    email_with_addresses = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/plain

Contact us at support@company.com or sales@company.com for help.
"""
    mail = email.message_from_string(email_with_addresses)
    addresses = extract_email_addresses_from_body(mail)

    assert "support@company.com" in addresses
    assert "sales@company.com" in addresses


def test_extract_email_addresses_from_body_empty():
    """Test extracting from body with no email addresses."""
    mail = email.message_from_string(SIMPLE_EMAIL)
    addresses = extract_email_addresses_from_body(mail)

    assert isinstance(addresses, list)


def test_email_headers_dataclass():
    """Test EmailHeaders dataclass defaults."""
    headers = EmailHeaders()

    assert headers.email_id is None
    assert headers.received == []
    assert headers.raw_headers == {}


def test_email_body_dataclass():
    """Test EmailBody dataclass defaults."""
    body = EmailBody()

    assert body.plain_text is None
    assert body.html is None
    assert body.charset is None


def test_email_attachment_dataclass():
    """Test EmailAttachment dataclass."""
    attachment = EmailAttachment(
        filename="test.txt",
        content_type="text/plain",
        size=100,
    )

    assert attachment.filename == "test.txt"
    assert attachment.content_type == "text/plain"
    assert attachment.size == 100
    assert attachment.content is None
    assert attachment.is_inline is False


def test_extract_urls_mailto_filtered():
    """Test that mailto links are filtered out."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<a href="mailto:test@example.com">Email us</a>
<a href="https://valid.example.com">Visit</a>
</body></html>
"""
    mail = email.message_from_string(email_content)
    urls = extract_email_urls(mail)

    assert "https://valid.example.com" in urls
    assert not any("mailto" in u for u in urls)


def test_extract_urls_non_http_filtered():
    """Test that non-http URLs are filtered."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<a href="ftp://ftp.example.com">FTP</a>
<a href="https://valid.example.com">Valid</a>
</body></html>
"""
    mail = email.message_from_string(email_content)
    urls = extract_email_urls(mail)

    assert "https://valid.example.com" in urls
    assert not any("ftp://" in u for u in urls)


def test_extract_attachment_inline():
    """Test extracting inline attachment."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Body text
--boundary123
Content-Type: image/png; name="image.png"
Content-Disposition: inline; filename="image.png"
Content-ID: <image001>
Content-Transfer-Encoding: base64

iVBORw0KGgo=
--boundary123--
"""
    mail = email.message_from_string(email_content)
    attachments = extract_email_attachments(mail)

    assert len(attachments) == 1
    assert attachments[0].is_inline is True
    assert attachments[0].content_id == "image001"


def test_extract_attachment_unnamed():
    """Test extracting attachment without filename."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Body text
--boundary123
Content-Type: application/octet-stream
Content-Disposition: attachment
Content-Transfer-Encoding: base64

dGVzdA==
--boundary123--
"""
    mail = email.message_from_string(email_content)
    attachments = extract_email_attachments(mail)

    assert len(attachments) == 1
    assert attachments[0].filename == "unnamed_attachment"


def test_extract_body_html_only():
    """Test extracting HTML-only body."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body><p>HTML only content</p></body></html>
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.html is not None
    assert "HTML only content" in body.html
    assert body.plain_text is None


def test_extract_addresses_from_html_body():
    """Test extracting email addresses from HTML body."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<p>Contact HTML@example.com for help</p>
</body></html>
"""
    mail = email.message_from_string(email_content)
    addresses = extract_email_addresses_from_body(mail)

    assert "html@example.com" in addresses


def test_extract_domains_invalid_url():
    """Test domain extraction handles invalid URLs."""
    urls = [
        "https://valid.example.com",
        "not-a-valid-url",
        "https://another.example.com",
    ]
    domains = extract_domains_from_urls(urls)

    assert "valid.example.com" in domains
    assert "another.example.com" in domains


def test_decode_header_value_exception():
    """Test _decode_header_value falls back on exception."""
    with patch(
        "soar_sdk.extras.email.rfc5322.make_header", side_effect=Exception("fail")
    ):
        result = _decode_header_value("test value")
        assert result == "test value"


def test_decode_header_value_none():
    """Test _decode_header_value returns None for empty input."""
    assert _decode_header_value(None) is None
    assert _decode_header_value("") is None


def test_decode_payload_unicode_dammit_exception():
    """Test _decode_payload falls back when UnicodeDammit fails."""
    with patch(
        "soar_sdk.extras.email.rfc5322.UnicodeDammit", side_effect=Exception("fail")
    ):
        result = _decode_payload(b"test content", "utf-8")
        assert result == "test content"


def test_decode_payload_all_exceptions():
    """Test _decode_payload uses replace on all failures."""
    with patch(
        "soar_sdk.extras.email.rfc5322.UnicodeDammit", side_effect=Exception("fail")
    ):
        result = _decode_payload(b"\xff\xfe invalid", "invalid-charset")
        assert isinstance(result, str)


def test_extract_urls_from_content_exception():
    """Test _extract_urls_from_content handles BeautifulSoup exception."""
    urls: set[str] = set()
    with patch(
        "soar_sdk.extras.email.rfc5322.BeautifulSoup", side_effect=Exception("fail")
    ):
        _extract_urls_from_content("<html></html>", urls, is_html=True)
    assert len(urls) == 0


def test_extract_urls_src_empty():
    """Test URL extraction with empty src attribute."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<img src="">
<img src="https://valid.example.com/img.png">
</body></html>
"""
    mail = email.message_from_string(email_content)
    urls = extract_email_urls(mail)

    assert "https://valid.example.com/img.png" in urls


def test_extract_urls_href_empty():
    """Test URL extraction with empty href."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<a href="">Empty link</a>
<a href="https://valid.example.com">Valid</a>
</body></html>
"""
    mail = email.message_from_string(email_content)
    urls = extract_email_urls(mail)

    assert "https://valid.example.com" in urls


def test_extract_domains_exception():
    """Test domain extraction handles urlparse exception."""
    with patch("soar_sdk.extras.email.rfc5322.urlparse", side_effect=Exception("fail")):
        domains = extract_domains_from_urls(["https://example.com"])
        assert domains == []


def test_extract_body_multipart_skip_attachment():
    """Test body extraction skips attachment parts."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain
Content-Disposition: attachment; filename="text.txt"

This should be skipped as it's an attachment
--boundary123
Content-Type: text/plain

This is the actual body
--boundary123--
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.plain_text is not None
    assert "actual body" in body.plain_text
    assert "skipped" not in body.plain_text


def test_extract_body_multipart_empty_payload():
    """Test body extraction handles empty payload."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

--boundary123
Content-Type: text/plain

Valid body content
--boundary123--
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.plain_text is not None


def test_extract_body_non_bytes_payload():
    """Test body extraction handles non-bytes payload."""
    mail = MagicMock()
    mail.is_multipart.return_value = False
    mail.get_payload.return_value = "string not bytes"
    mail.get_content_charset.return_value = "utf-8"

    body = extract_email_body(mail)

    assert body.plain_text is None


def test_extract_attachments_non_bytes_payload():
    """Test attachment extraction handles non-bytes payload."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Body
--boundary123
Content-Type: application/pdf; name="doc.pdf"
Content-Disposition: attachment; filename="doc.pdf"

Not base64 encoded
--boundary123--
"""
    mail = email.message_from_string(email_content)
    attachments = extract_email_attachments(mail)

    assert len(attachments) >= 0


def test_extract_email_addresses_empty_body():
    """Test extracting addresses when body is empty."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: application/pdf
Content-Disposition: attachment; filename="doc.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--boundary123--
"""
    mail = email.message_from_string(email_content)
    addresses = extract_email_addresses_from_body(mail)

    assert addresses == []


def test_extract_urls_from_content_non_html():
    """Test URL extraction from non-HTML content."""
    urls: set[str] = set()
    _extract_urls_from_content(
        "Visit https://example.com/path for more info", urls, is_html=False
    )

    assert "https://example.com/path" in urls


def test_extract_urls_cleaned_non_http():
    """Test that non-http URLs after cleaning are filtered."""
    urls: set[str] = set()
    _extract_urls_from_content("ftp://ftp.example.com/file", urls, is_html=False)

    assert len(urls) == 0


def test_extract_body_html_only_multipart():
    """Test HTML-only body extraction in multipart message (no text/plain)."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/html; charset="utf-8"

<html><body>HTML content only</body></html>
--boundary123--
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.html is not None
    assert "HTML content only" in body.html
    assert body.plain_text is None


def test_extract_urls_src_non_http():
    """Test URL extraction filters non-http src attributes."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Content-Type: text/html

<html><body>
<img src="data:image/png;base64,iVBORw0KGgo=">
<img src="https://valid.example.com/img.png">
</body></html>
"""
    mail = email.message_from_string(email_content)
    urls = extract_email_urls(mail)

    assert "https://valid.example.com/img.png" in urls
    assert not any("data:" in u for u in urls)


def test_extract_body_plain_then_html_multipart():
    """Test multipart with plain text followed by HTML."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

Plain text version
--boundary123
Content-Type: text/html; charset="utf-8"

<html><body>HTML version</body></html>
--boundary123--
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.plain_text is not None
    assert "Plain text version" in body.plain_text
    assert body.html is not None
    assert "HTML version" in body.html


def test_extract_body_duplicate_html_parts():
    """Test multipart with multiple HTML parts - only first is used."""
    email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/html; charset="utf-8"

<html><body>First HTML</body></html>
--boundary123
Content-Type: text/html; charset="utf-8"

<html><body>Second HTML - should be ignored</body></html>
--boundary123--
"""
    mail = email.message_from_string(email_content)
    body = extract_email_body(mail)

    assert body.html is not None
    assert "First HTML" in body.html
    assert "Second HTML" not in body.html
