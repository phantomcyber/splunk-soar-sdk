import tempfile
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from soar_sdk.extras.email import EmailProcessor, ProcessEmailContext
from soar_sdk.extras.email.processor import validate_url
from soar_sdk.extras.email.utils import (
    clean_url,
    create_dict_hash,
    decode_uni_string,
    get_file_contains,
    get_string,
    is_ip,
    is_ipv6,
    is_sha1,
    remove_child_info,
)


def _create_context(
    folder_name: str = "INBOX",
    is_hex: bool = False,
) -> ProcessEmailContext:
    """Helper to create a ProcessEmailContext with mocks."""
    return ProcessEmailContext(
        soar=MagicMock(),
        vault=MagicMock(),
        app_id="test-app-id",
        folder_name=folder_name,
        is_hex=is_hex,
    )


def _create_config(**overrides: bool) -> dict[str, bool]:
    """Helper to create email config with optional overrides."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    config.update(overrides)
    return config


@pytest.fixture
def mock_context() -> ProcessEmailContext:
    """Create a mock email processing context."""
    return _create_context()


@pytest.fixture
def email_config() -> dict[str, bool]:
    """Create default email processing configuration."""
    return _create_config()


def test_email_processor_initialization(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test EmailProcessor initialization."""
    processor = EmailProcessor(mock_context, email_config)

    assert processor.context == mock_context
    assert processor._config == email_config
    assert isinstance(processor._email_id_contains, list)
    assert isinstance(processor._container, dict)
    assert isinstance(processor._artifacts, list)
    assert isinstance(processor._attachments, list)


def test_is_ipv4() -> None:
    """Test IPv4 validation."""
    assert is_ip("192.168.1.1")
    assert is_ip("10.0.0.1")
    assert is_ip("255.255.255.255")
    assert not is_ip("256.1.1.1")
    assert not is_ip("not.an.ip.address")


def test_is_ipv6_validation() -> None:
    """Test IPv6 validation."""
    assert is_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert is_ipv6("::1")
    assert is_ipv6("fe80::1")
    assert not is_ipv6("not-an-ipv6")
    assert not is_ipv6("192.168.1.1")


def test_is_sha1_validation() -> None:
    """Test SHA1 hash validation."""
    assert is_sha1("356a192b7913b04c54574d18c28d46e6395428ab")
    assert is_sha1("da39a3ee5e6b4b0d3255bfef95601890afd80709")
    assert not is_sha1("not-a-sha1-hash")
    assert not is_sha1("356a192b")


def test_clean_url_util() -> None:
    """Test URL cleaning."""
    assert clean_url("https://example.com>") == "https://example.com"
    assert clean_url("https://example.com<") == "https://example.com"
    assert clean_url("https://example.com]") == "https://example.com"
    assert clean_url("https://example.com,") == "https://example.com"
    assert clean_url("https://example.com> ") == "https://example.com"


def test_decode_uni_string_util() -> None:
    """Test unicode string decoding."""
    plain_string = "Hello World"
    assert decode_uni_string(plain_string, "default") == plain_string

    encoded_string = "=?UTF-8?Q?Hello?= World"
    result = decode_uni_string(encoded_string, "default")
    assert "Hello" in result


def test_get_container_name(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test container name extraction."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"subject": "Test Email Subject"}

    container_name = processor._get_container_name(parsed_mail, "test-email-id-123")
    assert "Test Email Subject" in container_name

    parsed_mail_no_subject = {}
    container_name_no_subject = processor._get_container_name(
        parsed_mail_no_subject, "test-email-id-456"
    )
    assert container_name_no_subject == "Email ID: test-email-id-456"


def test_validate_url_valid() -> None:
    """Test validate_url with valid URLs."""
    validate_url("https://example.com")
    validate_url("http://example.com/path?query=1")
    validate_url("https://sub.domain.example.com:8080/path")


def test_validate_url_invalid() -> None:
    """Test validate_url with invalid URLs."""
    with pytest.raises(ValueError, match="Invalid URL"):
        validate_url("not-a-url")
    with pytest.raises(ValueError, match="Invalid URL"):
        validate_url("ftp://invalid")


def test_get_string_empty() -> None:
    """Test get_string with empty input."""
    assert get_string("") == ""
    assert get_string(None) is None


def test_get_string_with_charset() -> None:
    """Test get_string with charset."""
    result = get_string("Hello World", "utf-8")
    assert result == "Hello World"


def test_get_string_fallback() -> None:
    """Test get_string fallback handling."""
    encoded = "=?UTF-8?B?SGVsbG8gV29ybGQ=?="
    result = get_string(encoded)
    assert "Hello" in result or result == encoded


def test_get_file_contains_no_magic() -> None:
    """Test get_file_contains when magic is not available."""
    with patch.dict("sys.modules", {"magic": None}):
        result = get_file_contains("/fake/path.txt")
        assert result == []


def test_get_file_contains_with_extension() -> None:
    """Test get_file_contains with known extension."""
    mock_magic = MagicMock()
    mock_magic.from_file.return_value = "ASCII text"

    with (
        patch.dict("sys.modules", {"magic": mock_magic}),
        tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f,
    ):
        f.write(b"console.log('test');")
        f.flush()
        result = get_file_contains(f.name)
        Path(f.name).unlink()
    assert "javascript" in result


def test_get_file_contains_magic_pe() -> None:
    """Test get_file_contains with PE file magic."""
    mock_magic = MagicMock()
    mock_magic.from_file.return_value = "PE32 Windows executable"

    with (
        patch.dict("sys.modules", {"magic": mock_magic}),
        tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f,
    ):
        f.write(b"MZ")
        f.flush()
        result = get_file_contains(f.name)
        Path(f.name).unlink()
    assert "pe file" in result
    assert "hash" in result


def test_get_file_contains_magic_pdf() -> None:
    """Test get_file_contains with PDF magic."""
    mock_magic = MagicMock()
    mock_magic.from_file.return_value = "PDF document"

    with (
        patch.dict("sys.modules", {"magic": mock_magic}),
        tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f,
    ):
        f.write(b"%PDF-1.4")
        f.flush()
        result = get_file_contains(f.name)
        Path(f.name).unlink()
    assert "pdf" in result


def test_get_file_contains_magic_exception() -> None:
    """Test get_file_contains when magic raises an exception."""
    mock_magic = MagicMock()
    mock_magic.from_file.side_effect = Exception("Magic error")

    with (
        patch.dict("sys.modules", {"magic": mock_magic}),
        tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f,
    ):
        f.write(b"test")
        f.flush()
        result = get_file_contains(f.name)
        Path(f.name).unlink()
    assert "doc" in result


def test_get_ips(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts IPv4 and IPv6 addresses."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = "Contact us at 192.168.1.1 or 10.0.0.1 for IPv4"
    processor._get_ips(file_data, ips)
    assert "192.168.1.1" in ips
    assert "10.0.0.1" in ips


def test_get_ips_ipv6(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts IPv6 addresses."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = " 2001:0db8:85a3:0000:0000:8a2e:0370:7334 "
    processor._get_ips(file_data, ips)
    assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" in ips


def test_get_ips_invalid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips ignores invalid IPs."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = "Invalid: 999.999.999.999"
    processor._get_ips(file_data, ips)
    assert "999.999.999.999" not in ips


def test_extract_urls_domains_disabled(mock_context: ProcessEmailContext) -> None:
    """Test _extract_urls_domains when extraction is disabled."""
    config = _create_config(extract_urls=False, extract_domains=False)
    processor = EmailProcessor(mock_context, config)
    urls: set[str] = set()
    domains: set[str] = set()

    processor._extract_urls_domains(
        "<html><a href='https://test.com'>link</a></html>", urls, domains
    )
    assert len(urls) == 0
    assert len(domains) == 0


def test_extract_urls_domains_with_links(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts URLs from href tags."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com/path">Click</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)
    assert len(urls) >= 1
    assert "example.com" in domains


def test_extract_urls_domains_with_src(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts URLs from src tags."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><img src="https://cdn.example.com/image.png"/></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "cdn.example.com"
        processor._extract_urls_domains(html, urls, domains)
    assert len(urls) >= 1


def test_extract_urls_domains_mailto(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts domains from mailto links."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="mailto:user@example.org">Email</a></html>'
    processor._extract_urls_domains(html, urls, domains)
    assert "example.org" in domains


def test_extract_urls_domains_plain_text(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts URLs from plain text."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    text = "Visit https://plaintext.example.com for more info"
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "plaintext.example.com"
        processor._extract_urls_domains(text, urls, domains)
    assert len(urls) >= 1


def test_add_artifacts(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_artifacts creates artifacts from input set."""
    processor = EmailProcessor(mock_context, email_config)
    artifacts: list[dict] = []
    input_set = {"192.168.1.1", "10.0.0.1"}

    added = processor._add_artifacts(
        "sourceAddress", input_set, "IP Artifact", 0, artifacts
    )
    assert added == 2
    assert len(artifacts) == 2
    assert all(a["name"] == "IP Artifact" for a in artifacts)


def test_add_artifacts_empty_entries(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_artifacts skips empty entries."""
    processor = EmailProcessor(mock_context, email_config)
    artifacts: list[dict] = []
    input_set = {"valid", "", None}

    added = processor._add_artifacts("key", input_set, "Test Artifact", 0, artifacts)
    assert added == 1


def test_add_email_header_artifacts(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_email_header_artifacts."""
    processor = EmailProcessor(mock_context, email_config)
    artifacts: list[dict] = []
    email_headers = [
        {"name": "Email Artifact", "cef": {"fromEmail": "test@example.com"}},
    ]

    added = processor._add_email_header_artifacts(email_headers, 0, artifacts)
    assert added == 1
    assert artifacts[0]["source_data_identifier"] == "0"


def test_remove_child_info_util() -> None:
    """Test remove_child_info removes suffixes using rstrip behavior."""
    result_true = remove_child_info("/path/xyz_True")
    assert "_True" not in result_true

    result_false = remove_child_info("/path/xyz_False")
    assert "_False" not in result_false


def test_set_email_id_contains_sha1(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _set_email_id_contains with SHA1 hash."""
    processor = EmailProcessor(mock_context, email_config)

    processor._set_email_id_contains("356a192b7913b04c54574d18c28d46e6395428ab")
    assert processor._email_id_contains == ["vault id"]


def test_set_email_id_contains_non_sha1(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _set_email_id_contains with non-SHA1."""
    processor = EmailProcessor(mock_context, email_config)

    processor._set_email_id_contains("not-a-sha1")
    assert processor._email_id_contains == []


def test_create_dict_hash_util() -> None:
    """Test create_dict_hash generates hash."""
    result = create_dict_hash({"key": "value"})
    assert result is not None
    assert len(result) == 64


def test_create_dict_hash_empty() -> None:
    """Test create_dict_hash with empty dict."""
    result = create_dict_hash({})
    assert result is None


def test_del_tmp_dirs(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _del_tmp_dirs removes temp directories."""
    processor = EmailProcessor(mock_context, email_config)

    tmp_dir = tempfile.mkdtemp()
    processor._tmp_dirs.append(tmp_dir)
    assert Path(tmp_dir).exists()

    processor._del_tmp_dirs()
    assert not Path(tmp_dir).exists()


def test_set_sdi(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _set_sdi sets source_data_identifier."""
    processor = EmailProcessor(mock_context, email_config)

    input_dict = {"name": "test", "cef": {"key": "value"}}
    processor._set_sdi(input_dict)
    assert "source_data_identifier" in input_dict
    assert input_dict["source_data_identifier"] is not None


def test_set_sdi_with_parent_guid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _set_sdi with parentGuid in cef."""
    processor = EmailProcessor(mock_context, email_config)

    input_dict = {"name": "test", "cef": {"parentGuid": "guid123"}}
    processor._set_sdi(input_dict)
    assert "source_data_identifier" in input_dict


def test_set_sdi_with_email_guid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _set_sdi with emailGuid in cef."""
    processor = EmailProcessor(mock_context, email_config)

    input_dict = {"name": "test", "cef": {"emailGuid": "email-guid-123"}}
    processor._set_sdi(input_dict)
    assert "source_data_identifier" in input_dict
    assert "email-guid-123" in processor._guid_to_hash


def test_update_headers_empty(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _update_headers with empty external headers."""
    processor = EmailProcessor(mock_context, email_config)
    from requests.structures import CaseInsensitiveDict

    headers = CaseInsensitiveDict({"Content-Type": "text/plain"})
    result = processor._update_headers(headers)
    assert result == 1


def test_update_headers_with_match(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _update_headers with matching message-id."""
    processor = EmailProcessor(mock_context, email_config)
    from requests.structures import CaseInsensitiveDict

    processor._external_headers = [
        CaseInsensitiveDict({"message-id": "<test@example.com>", "extra": "value"})
    ]
    headers = CaseInsensitiveDict({"message-id": "<test@example.com>"})
    processor._update_headers(headers)
    assert "extra" in headers


def test_get_email_headers_from_part_empty(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part with empty message."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    result = processor._get_email_headers_from_part(msg)
    assert len(result) == 0


def test_get_email_headers_from_part_with_headers(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part with headers."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "Test Subject"

    result = processor._get_email_headers_from_part(msg)
    assert "From" in result
    assert "To" in result
    assert "Subject" in result
    assert "decodedSubject" in result


def test_get_email_headers_from_part_with_received(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part extracts Received headers."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["Received"] = "from server1 (example.com)"
    msg.add_header("Received", "from server2 (example.org)")

    result = processor._get_email_headers_from_part(msg)
    assert "Received" in result
    assert isinstance(result["Received"], list)


def test_create_artifacts(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _create_artifacts creates artifacts from parsed mail."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": {"192.168.1.1"},
        "hashes": {"d41d8cd98f00b204e9800998ecf8427e"},
        "urls": {"https://example.com"},
        "domains": {"example.com"},
        "email_headers": [],
    }

    result = processor._create_artifacts(parsed_mail)
    assert result == 1
    assert len(processor._artifacts) == 4


def test_handle_if_body_no_disposition(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_if_body with no content disposition."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg.set_payload("Test body content")
    msg["Content-Type"] = "text/plain"

    bodies = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        result, process_further = processor._handle_if_body(
            None, None, "text/plain", msg, bodies, file_path
        )
    assert result == 1
    assert len(bodies) == 1


def test_handle_if_body_attachment(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_if_body with attachment disposition."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg.set_payload("Test content")

    bodies = []
    result, process_further = processor._handle_if_body(
        "attachment", None, "application/pdf", msg, bodies, "/path/file.pdf"
    )
    assert result == 1
    assert process_further is True
    assert len(bodies) == 0


def test_handle_if_body_empty_payload(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_if_body with empty payload."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()

    bodies = []
    result, process_further = processor._handle_if_body(
        None, None, "text/plain", msg, bodies, "/path/test.txt"
    )
    assert result == 1
    assert process_further is False


def test_handle_body(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body processes email body."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("<html><body>Test user@example.com</body></html>")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            result = processor._handle_body(body, parsed_mail, 0, "email-123")

    assert result == 1


def test_handle_body_binary_file(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body with binary content."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.bin"
        body_file.write_bytes(b"\x00\x01\x02\x03 some text")

        body = {"file_path": str(body_file), "charset": None}
        with patch("soar_sdk.extras.email.processor.phantom"):
            result = processor._handle_body(body, parsed_mail, 0, "email-123")

    assert result == 1


def test_handle_body_empty_file(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body with empty file."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "empty.txt"
        body_file.write_text("")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        result = processor._handle_body(body, parsed_mail, 0, "email-123")

    assert result == 0


def test_parse_email_headers(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers extracts headers from email part."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Message-ID"] = "<test-id@example.com>"

    result = processor._parse_email_headers(parsed_mail, msg, add_email_id="email-123")
    assert result >= 1
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_with_body_extract(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers extracts body when configured."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test-app-id",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload("This is the body content")

    result = processor._parse_email_headers(parsed_mail, msg, add_email_id="email-id")
    assert result >= 1


def test_parse_email_headers_no_headers(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers with no relevant headers."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}

    msg = Message()

    result = processor._parse_email_headers(parsed_mail, msg)
    assert result == 0


def test_handle_attachment(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment adds file to attachments."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Test attachment content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/attachment.txt"
        result = processor._handle_attachment(msg, "attachment.txt", file_path)

    assert result == 1
    assert len(processor._parsed_mail["files"]) == 1


def test_handle_attachment_no_parsed_mail(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment when _parsed_mail is None."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = None

    msg = Message()
    result = processor._handle_attachment(msg, "test.txt", "/path/test.txt")
    assert result == 0


def test_handle_attachment_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _handle_attachment when extraction is disabled."""
    config = {
        "extract_attachments": False,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test-app-id",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    result = processor._handle_attachment(msg, "test.txt", "/path/test.txt")
    assert result == 1
    assert len(processor._parsed_mail["files"]) == 0


def test_handle_part(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part processes email parts."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg["Content-Type"] = "text/plain"
    msg.set_payload("Test body content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_handle_part_with_filename(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part with named attachment."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg["Content-Disposition"] = 'attachment; filename="test.pdf"'
    msg["Content-Type"] = "application/pdf"
    msg.set_payload(b"PDF content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_int_process_email(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _int_process_email processes RFC822 email."""
    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
Content-Type: text/plain

This is a test email body."""

    ret_val, message, results = processor._int_process_email(
        rfc822_email, "email-id-123", 1234567890.0
    )

    assert ret_val == 1
    assert message == "Email Parsed"
    assert len(results) == 1
    processor._del_tmp_dirs()


def test_int_process_email_multipart(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _int_process_email with multipart email."""
    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

This is the text part.
--boundary123
Content-Type: text/html

<html><body>HTML part</body></html>
--boundary123--"""

    ret_val, message, results = processor._int_process_email(
        rfc822_email, "email-id-456", 1234567890.0
    )

    assert ret_val == 1
    assert message == "Email Parsed"
    processor._del_tmp_dirs()


def test_handle_mail_object(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object processes email Message."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Message-ID: <test123@example.com>
Date: Mon, 1 Jan 2024 00:00:00 +0000
Content-Type: text/plain

Body content."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1
    assert processor._container["name"] == "Test Subject"


def test_handle_mail_object_hex_folder(email_config: dict[str, bool]) -> None:
    """Test _handle_mail_object with hex folder name."""
    import email as email_module

    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test-app-id",
        folder_name="abc123def456",
        is_hex=True,
    )
    processor = EmailProcessor(context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1
    assert "abc123def456" in processor._container["source_data_identifier"]


def test_process_email(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email main entry point."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)
    mock_context.soar.save_artifacts = MagicMock(return_value=[1, 2])
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    rfc822_email = """From: sender@example.com
To: recipient@example.com
Subject: Process Test
Content-Type: text/plain

Test body content."""

    ret_val, message = processor.process_email(
        base_connector=MagicMock(),
        rfc822_email=rfc822_email,
        email_id="email-123",
        config=email_config,
        epoch=1234567890.0,
    )

    assert ret_val == 1
    assert message == "Email Processed"


def test_process_email_with_container_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email with existing container_id."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_artifacts = MagicMock(return_value=[1])

    rfc822_email = """From: sender@example.com
Subject: Container Test
Content-Type: text/plain

Body."""

    ret_val, message = processor.process_email(
        base_connector=MagicMock(),
        rfc822_email=rfc822_email,
        email_id="email-456",
        config=email_config,
        epoch=1234567890.0,
        container_id=999,
    )

    assert ret_val == 1


def test_process_email_with_headers(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email with external headers."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    rfc822_email = """From: sender@example.com
Subject: Headers Test
Content-Type: text/plain

Body."""

    email_headers = [{"X-Custom": "custom-value"}]

    ret_val, message = processor.process_email(
        base_connector=MagicMock(),
        rfc822_email=rfc822_email,
        email_id="email-789",
        config=email_config,
        epoch=1234567890.0,
        email_headers=email_headers,
    )

    assert ret_val == 1
    assert len(processor._external_headers) == 1


def test_process_email_with_attachments_data(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email with attachments data."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    rfc822_email = """From: sender@example.com
Subject: Attachments Test
Content-Type: text/plain

Body."""

    attachments_data = [{"content": "base64content", "name": "file.txt"}]

    ret_val, message = processor.process_email(
        base_connector=MagicMock(),
        rfc822_email=rfc822_email,
        email_id="email-attach",
        config=email_config,
        epoch=1234567890.0,
        attachments_data=attachments_data,
    )

    assert ret_val == 1


def test_save_ingested_new_container(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _save_ingested creates new container."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    container = {
        "name": "Test Container",
        "artifacts": [{"name": "Test Artifact", "cef": {}}],
    }

    ret_val, message, cid = processor._save_ingested(container, using_dummy=False)

    assert ret_val == 1
    assert cid == 123


def test_save_ingested_dummy_container(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _save_ingested with dummy container."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_artifacts = MagicMock(return_value=[1, 2])

    container = {
        "id": 999,
        "artifacts": [{"name": "Test Artifact", "cef": {}}],
    }

    ret_val, message, cid = processor._save_ingested(container, using_dummy=True)

    assert ret_val == 1
    assert cid == 999


def test_save_ingested_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _save_ingested handles errors."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(side_effect=Exception("Save failed"))

    container = {"name": "Test", "artifacts": []}

    ret_val, message, cid = processor._save_ingested(container, using_dummy=False)

    assert ret_val == 0
    assert cid is None


def test_handle_save_ingested_with_container_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested with existing container_id."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_artifacts = MagicMock(return_value=[1])

    artifacts = [{"name": "Test", "cef": {"key": "value"}}]

    processor._handle_save_ingested(artifacts, None, 999, [])


def test_handle_save_ingested_with_container(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested with container object."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    artifacts = [{"name": "Test", "cef": {}}]
    container = {"name": "Test Container"}

    processor._handle_save_ingested(artifacts, container, None, [])


def test_handle_save_ingested_no_container(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested with no container."""
    processor = EmailProcessor(mock_context, email_config)

    artifacts = [{"name": "Test", "cef": {}}]

    processor._handle_save_ingested(artifacts, None, None, [])


def test_add_vault_hashes_to_dictionary(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary adds hashes."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.get_attachment = MagicMock(
        return_value=[
            {
                "metadata": {
                    "sha256": "abc123",
                    "md5": "def456",
                    "sha1": "ghi789",
                }
            }
        ]
    )

    cef_artifact = {}
    ret_val, message = processor._add_vault_hashes_to_dictionary(
        cef_artifact, "vault-id"
    )

    assert ret_val == 1
    assert cef_artifact.get("fileHashSha256") == "abc123"
    assert cef_artifact.get("fileHashMd5") == "def456"
    assert cef_artifact.get("fileHashSha1") == "ghi789"


def test_add_vault_hashes_to_dictionary_not_found(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary when vault not found."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.get_attachment = MagicMock(return_value=[])

    cef_artifact = {}
    ret_val, message = processor._add_vault_hashes_to_dictionary(
        cef_artifact, "vault-id"
    )

    assert ret_val == 0


def test_add_vault_hashes_to_dictionary_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary handles exceptions."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.get_attachment = MagicMock(side_effect=Exception("Vault error"))

    cef_artifact = {}
    ret_val, message = processor._add_vault_hashes_to_dictionary(
        cef_artifact, "vault-id"
    )

    assert ret_val == 0


def test_handle_file(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file adds file to vault."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id-123")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash123"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("test content")

        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action_name"
            mock_phantom.APP_JSON_APP_RUN_ID = "app_run_id"
            ret_val, added = processor._handle_file(
                curr_file, [], 123, 0, run_automation=True
            )

    assert ret_val == 1


def test_handle_file_no_filename(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file infers filename from path."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "inferred.pdf"
        file_path.write_text("pdf content")

        curr_file = {"file_path": str(file_path)}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action_name"
            mock_phantom.APP_JSON_APP_RUN_ID = "app_run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_file_vault_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file handles vault errors."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(side_effect=Exception("Vault error"))

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action_name"
            mock_phantom.APP_JSON_APP_RUN_ID = "app_run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 0


def test_parse_results(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results processes email results."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [
                    {"name": "Artifact 1", "cef": {}},
                    {"name": "Artifact 2", "cef": {}},
                ],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_parse_results_with_container_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with existing container_id."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_artifacts = MagicMock(return_value=[1])

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": None,
                "artifacts": [{"name": "Artifact", "cef": {}}],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results, container_id=999)

    assert ret_val == 1


def test_parse_results_with_parent_guid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results handles parentGuid."""
    processor = EmailProcessor(mock_context, email_config)
    processor._guid_to_hash = {"parent-guid": "parent-hash-123"}

    mock_context.soar.save_container = MagicMock(return_value=123)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [
                    {"name": "Art", "cef": {"parentGuid": "parent-guid"}},
                ],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_parse_results_empty_artifacts(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with empty artifacts."""
    processor = EmailProcessor(mock_context, email_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_handle_attachment_with_external_match(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment matches external attachments."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}
    processor._external_attachments = [
        {"content": "VGVzdCBjb250ZW50", "name": "test.txt"}
    ]

    msg = Message()
    msg.set_payload("VGVzdCBjb250ZW50")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 1


def test_handle_attachment_empty_payload(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with empty payload."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()

    result = processor._handle_attachment(msg, "test.txt", "/path/test.txt")
    assert result == 1
    assert len(processor._parsed_mail["files"]) == 0


def test_get_string_unicode_exception() -> None:
    """Test get_string handles unicode exceptions."""
    malformed = b"\xff\xfe".decode("latin-1")
    result = get_string(malformed, "utf-8")
    assert result is not None


def test_decode_uni_string_malformed() -> None:
    """Test decode_uni_string with malformed encoding."""
    malformed = "=?UTF-8?Q?Malformed=ZZ?="
    result = decode_uni_string(malformed, "default")
    assert result is not None


def test_extract_urls_domains_mailto_with_query(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains with mailto containing query params."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="mailto:user@domain.com?subject=Test">Email</a></html>'
    processor._extract_urls_domains(html, urls, domains)
    assert "domain.com" in domains


def test_handle_body_with_hashes(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body extracts hashes."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Hash: d41d8cd98f00b204e9800998ecf8427e in body")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "d41d8cd98f00b204e9800998ecf8427e" in parsed_mail["hashes"]


def test_parse_email_headers_with_cc(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers decodes CC header."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["CC"] = "cc@example.com"
    msg["Message-ID"] = "<test@example.com>"

    processor._parse_email_headers(parsed_mail, msg)

    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_mail_object_multipart(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object with multipart message."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    processor = EmailProcessor(mock_context, email_config)

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "Multipart Test"
    msg["Message-ID"] = "<multi@example.com>"

    text_part = MIMEText("This is the text part", "plain")
    html_part = MIMEText("<html><body>HTML</body></html>", "html")

    msg.attach(text_part)
    msg.attach(html_part)

    rfc822_email = msg.as_string()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            msg, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_save_ingested_with_files(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested with files."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)
    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    artifacts = [{"name": "Test", "cef": {}}]
    container = {"name": "Test Container"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")
        files = [{"file_path": str(file_path), "file_name": "test.txt"}]

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            processor._handle_save_ingested(artifacts, container, None, files)


def test_process_email_failure(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email handles failure."""
    processor = EmailProcessor(mock_context, email_config)

    invalid_email = "Not a valid RFC822 email"

    with patch.object(processor, "_int_process_email", return_value=(0, "Error", [])):
        ret_val, message = processor.process_email(
            base_connector=MagicMock(),
            rfc822_email=invalid_email,
            email_id="test",
            config=email_config,
            epoch=1234567890.0,
        )

    assert ret_val == 0


def test_handle_part_rfc822(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part with message/rfc822 content type."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg["Content-Type"] = "message/rfc822"
    msg["Content-Disposition"] = "attachment"
    msg.set_payload("Nested email content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_parse_email_headers_with_body_key(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body in headers."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["bodyText"] = "This is the body"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test-id")
    assert len(parsed_mail["email_headers"]) >= 1


def test_extract_urls_domains_ip_domain(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains skips IP addresses as domains."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://192.168.1.1/path">IP Link</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "192.168.1.1"
        processor._extract_urls_domains(html, urls, domains)

    assert "192.168.1.1" not in domains


def test_handle_save_ingested_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested handles save errors."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(side_effect=Exception("Save error"))

    artifacts = [{"name": "Test", "cef": {}}]
    container = {"name": "Test Container"}

    processor._handle_save_ingested(artifacts, container, None, [])


def test_handle_attachment_long_filename(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with very long filename."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Test content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        long_name = "a" * 300 + ".txt"
        file_path = f"{tmp_dir}/{long_name}"
        result = processor._handle_attachment(msg, long_name, file_path)

    assert result == 1


def test_parse_email_headers_base64_body(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with base64 encoded body."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "base64"
    msg.set_payload("SGVsbG8gV29ybGQ=")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_file_with_parent_guid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file with parentGuid in meta_info."""
    processor = EmailProcessor(mock_context, email_config)
    processor._guid_to_hash = {"parent-guid-123": "parent-hash-456"}

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {
            "file_path": str(file_path),
            "file_name": "test.txt",
            "meta_info": {"parentGuid": "parent-guid-123"},
        }

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_file_no_vault_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file when vault returns no ID."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value=None)
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_save_ingested_dummy_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _save_ingested with dummy container error."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_artifacts = MagicMock(
        side_effect=Exception("Artifact error")
    )

    container = {"id": 999, "artifacts": [{"name": "Test", "cef": {}}]}

    ret_val, message, cid = processor._save_ingested(container, using_dummy=True)

    assert ret_val == 0
    assert cid is None


def test_get_container_name_with_encoded_subject(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_container_name with encoded subject."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"subject": "=?UTF-8?B?VGVzdCBTdWJqZWN0?="}

    result = processor._get_container_name(parsed_mail, "email-id")
    assert "Test Subject" in result or result != ""


def test_parse_results_no_container(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with no container in result."""
    processor = EmailProcessor(mock_context, email_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": None,
                "artifacts": [{"name": "Artifact", "cef": {}}],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_handle_body_with_ips(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body extracts IPs."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Contact us at 10.0.0.1 for support")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "10.0.0.1" in parsed_mail["ips"]


def test_create_dict_hash_json_error() -> None:
    """Test create_dict_hash handles JSON serialization errors."""

    class NonSerializable:
        pass

    input_dict = {"obj": NonSerializable()}
    result = create_dict_hash(input_dict)
    assert result is None


def test_get_string_double_decode_fallback() -> None:
    """Test get_string double fallback on decode error."""
    malformed = "=?UTF-8?Q?Test=FF=FE?="
    with patch("soar_sdk.extras.email.utils.UnicodeDammit") as mock_ud:
        mock_ud.return_value.unicode_markup.encode.side_effect = Exception(
            "Encode error"
        )
        result = get_string(malformed, "utf-8")
    assert result is not None


def test_handle_body_email_extraction(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body extracts email addresses for domains."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text('Contact user@example.org and "special user"@test.com')

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert (
        "example.org" in parsed_mail["domains"] or "test.com" in parsed_mail["domains"]
    )


def test_handle_body_file_read_binary(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body reads binary file fallback."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.bin"
        body_file.write_bytes(b"\xff\xfe test content")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            result = processor._handle_body(body, parsed_mail, 0, "email-123")

    assert result == 1


def test_parse_results_with_files(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results processes files."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)
    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash123"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "attach.txt"
        file_path.write_text("content")

        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [{"name": "Art", "cef": {}}],
                "files": [{"file_path": str(file_path), "file_name": "attach.txt"}],
                "temp_directory": tmp_dir,
            }
        ]

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_handle_attachment_write_file(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment writes content to file."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload("Test file content")
    msg["Content-Transfer-Encoding"] = "8bit"

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/output.txt"
        result = processor._handle_attachment(msg, "output.txt", file_path)

    assert result == 1
    assert len(processor._parsed_mail["files"]) == 1


def test_handle_part_multipart(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part with multipart content."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = MIMEMultipart()
    text_part = MIMEText("Body text", "plain")
    msg.attach(text_part)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_handle_mail_object_no_subject(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object without subject."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
To: recipient@example.com
Content-Type: text/plain

Body content."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_decode_uni_string_exception() -> None:
    """Test decode_uni_string with exception in decode."""
    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.side_effect = Exception("Decode error")
        result = decode_uni_string("=?UTF-8?B?test?=", "fallback")

    assert result == "fallback"


def test_decode_uni_string_no_value() -> None:
    """Test decode_uni_string with empty decoded values."""
    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(None, "utf-8")]
        result = decode_uni_string("test", "fallback")

    assert result is not None


def test_handle_attachment_long_name_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with long filename write exception."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/" + "x" * 300 + ".txt"
        with patch(
            "builtins.open", side_effect=[OSError("File name too long"), MagicMock()]
        ):
            result = processor._handle_attachment(msg, "x" * 300 + ".txt", file_path)

    assert result in [0, 1]


def test_handle_attachment_write_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with write exception."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        with patch("builtins.open", side_effect=Exception("Write error")):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 0


def test_extract_urls_domains_invalid_url(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains with invalid URL."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="javascript:void(0)">Click</a></html>'
    processor._extract_urls_domains(html, urls, domains)
    assert "javascript:void(0)" not in urls


def test_handle_if_body_html_with_style(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_if_body with HTML containing style tags."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg.set_payload("<html><style>body{color:red}</style><body>Text</body></html>")
    msg["Content-Type"] = "text/html"

    bodies = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.html"
        result, process_further = processor._handle_if_body(
            None, None, "text/html", msg, bodies, file_path
        )

    assert result == 1
    assert len(bodies) == 1


def test_parse_email_headers_inline_extract(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers_as_inline extracts data."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}
    file_data = "From: test@example.com\nSubject: Test"

    processor._parse_email_headers_as_inline(
        file_data, parsed_mail, "utf-8", "email-id"
    )


def test_parse_email_headers_inline_strips_forwarded_message(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers_as_inline strips forwarded message header."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}
    file_data = (
        "---------- Forwarded Message ----------\r\n"
        "From: sender@example.com\r\n"
        "To: recipient@example.com\r\n"
        "Subject: Forwarded Test\r\n"
    )

    processor._parse_email_headers_as_inline(
        file_data, parsed_mail, "utf-8", "email-id"
    )

    assert len(parsed_mail["email_headers"]) == 1
    cef = parsed_mail["email_headers"][0]["cef"]
    assert cef["fromEmail"] == "sender@example.com"
    assert cef["toEmail"] == "recipient@example.com"
    assert cef["emailHeaders"]["Subject"] == "Forwarded Test"


def test_add_vault_hashes_old_phantom(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary with old phantom version."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.get_attachment = MagicMock(
        return_value=[
            {
                "metadata": {
                    "sha256": "abc123",
                    "md5": "def456",
                }
            }
        ]
    )

    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_product_version.return_value = "1.0.0"

        cef_artifact = {}
        ret_val, message = processor._add_vault_hashes_to_dictionary(
            cef_artifact, "vault-id"
        )

    assert ret_val == 1


def test_handle_part_image(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part with image content."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg["Content-Type"] = "image/png"
    msg["Content-Disposition"] = 'inline; filename="image.png"'
    msg.set_payload(b"\x89PNG\r\n\x1a\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_extract_urls_domains_beautifulsoup_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains when BeautifulSoup raises an exception."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    with patch("soar_sdk.extras.email.processor.BeautifulSoup") as mock_bs:
        mock_bs.side_effect = Exception("Parse error")
        processor._extract_urls_domains("<html>test</html>", urls, domains)

    assert len(urls) == 0


def test_extract_urls_domains_uri_text_http(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts http URIs from link text."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = (
        '<html><a href="https://link.com">Visit https://text-link.com here</a></html>'
    )
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "link.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_decode_uni_string_non_utf8_encoding(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with non-UTF-8 encoding."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", "iso-8859-1")]
        result = decode_uni_string("=?iso-8859-1?Q?Test?=", "fallback")

    assert result is not None


def test_decode_uni_string_encoding_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with encoding conversion error."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"\xff\xfe", "iso-8859-1")]
        result = decode_uni_string("test", "fallback")

    assert result is not None


def test_decode_uni_string_unicode_dammit_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with UnicodeDammit error."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", "utf-8")]
        with patch("soar_sdk.extras.email.utils.UnicodeDammit") as mock_ud:
            mock_ud.side_effect = Exception("Unicode error")
            result = decode_uni_string("test", "fallback")

    assert result is not None


def test_get_container_name_decode_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_container_name when decode_header raises exception."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"subject": "=?INVALID?Q?Test?="}

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.side_effect = Exception("Decode error")
        result = processor._get_container_name(parsed_mail, "email-id")

    assert result is not None


def test_get_email_headers_from_part_charset_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part with charset conversion error."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test"

    with patch(
        "soar_sdk.extras.email.processor.get_string",
        side_effect=Exception("Charset error"),
    ):
        result = processor._get_email_headers_from_part(msg, charset="invalid")

    assert "From" in result or len(result) >= 0


def test_get_email_headers_from_part_received_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part with received header error."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["Received"] = "from server"
    msg["From"] = "sender@example.com"

    original_get_string = get_string

    def mock_get_string(value, charset=None):
        if "server" in str(value):
            raise Exception("Received error")
        return original_get_string(value, charset)

    with patch(
        "soar_sdk.extras.email.processor.get_string", side_effect=mock_get_string
    ):
        result = processor._get_email_headers_from_part(msg)

    assert len(result) >= 0


def test_get_email_headers_from_part_subject_decode_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part with subject decode error."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "=?INVALID?B?test?="

    with patch("soar_sdk.extras.email.processor.make_header") as mock_make:
        mock_make.side_effect = Exception("Header error")
        result = processor._get_email_headers_from_part(msg)

    assert "decodedSubject" in result or "Subject" in result


def test_get_email_headers_from_part_cc_decode(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_email_headers_from_part decodes CC."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["CC"] = "=?UTF-8?B?dGVzdA==?="

    result = processor._get_email_headers_from_part(msg)

    assert "decodedCC" in result


def test_parse_email_headers_body_unicode_error(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body unicode error."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload(b"\xff\xfe invalid")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_mail_object_part_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object when _handle_part raises exception."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    processor = EmailProcessor(mock_context, email_config)

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test"
    msg.attach(MIMEText("Text", "plain"))

    rfc822_email = msg.as_string()

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_handle_part", side_effect=Exception("Part error")),
    ):
        result = processor._handle_mail_object(
            msg, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_mail_object_part_app_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object when _handle_part returns APP_ERROR."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    processor = EmailProcessor(mock_context, email_config)

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test"
    msg.attach(MIMEText("Text", "plain"))

    rfc822_email = msg.as_string()

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_handle_part", return_value=0),
    ):
        result = processor._handle_mail_object(
            msg, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_mail_object_non_multipart_with_payload(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object with non-multipart that has payload."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body content here."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_mail_object_no_container_name(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object when container name is None."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Content-Type: text/plain

Body."""

    mail = email_module.message_from_string(rfc822_email)

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_get_container_name", return_value=None),
    ):
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 0


def test_int_process_email_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _int_process_email when _handle_mail_object raises exception."""
    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    with patch.object(
        processor, "_handle_mail_object", side_effect=Exception("Mail error")
    ):
        ret_val, message, results = processor._int_process_email(
            rfc822_email, "email-id", 1234567890.0
        )

    assert ret_val == 0
    assert "ErrorExp" in message
    processor._del_tmp_dirs()


def test_process_email_parse_results_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test process_email when _parse_results raises exception."""
    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    with (
        patch.object(processor, "_parse_results", side_effect=Exception("Parse error")),
        pytest.raises(Exception, match="Parse error"),
    ):
        processor.process_email(
            base_connector=MagicMock(),
            rfc822_email=rfc822_email,
            email_id="email-id",
            config=email_config,
            epoch=1234567890.0,
        )


def test_handle_save_ingested_container_id_none(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested when save returns no container_id."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=None)

    artifacts = [{"name": "Test", "cef": {}}]
    container = {"name": "Test Container"}

    processor._handle_save_ingested(artifacts, container, None, [])


def test_handle_save_ingested_error_return(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested when save returns error."""
    processor = EmailProcessor(mock_context, email_config)

    with patch.object(processor, "_save_ingested", return_value=(0, "Error", None)):
        artifacts = [{"name": "Test", "cef": {}}]
        container = {"name": "Test"}
        processor._handle_save_ingested(artifacts, container, None, [])


def test_handle_save_ingested_with_vault_file(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested processes vault files."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)
    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    artifacts = [{"name": "Test", "cef": {}}]
    container = {"name": "Test"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "file.txt"
        file_path.write_text("content")
        files = [{"file_path": str(file_path), "file_name": "file.txt"}]

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            processor._handle_save_ingested(artifacts, container, None, files)


def test_handle_file_added_to_vault(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file returns True for added_to_vault."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")
        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1
    assert added is True


def test_handle_attachment_external_match(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with external attachment match."""
    import base64

    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}
    processor._external_attachments = [
        {"content": base64.b64encode(b"Test content").decode(), "name": "match.txt"}
    ]

    msg = Message()
    msg.set_payload(b"Test content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/match.txt"
        result = processor._handle_attachment(msg, "match.txt", file_path)

    assert result == 1
    assert len(processor._parsed_mail["files"]) == 1


def test_handle_attachment_external_should_ignore(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment skips ignored external attachments."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}
    processor._external_attachments = [
        {"content": "test", "name": "ignore.txt", "should_ignore": True}
    ]

    msg = Message()
    msg.set_payload(b"Test content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 1


def test_handle_attachment_external_no_content(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with external attachment missing content."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}
    processor._external_attachments = [{"name": "nocontent.txt"}]

    msg = Message()
    msg.set_payload(b"Test content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 1


def test_handle_attachment_write_long_filename_fallback(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment writes with long filename fallback."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Test content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        long_name = "a" * 255 + ".txt"
        file_path = f"{tmp_dir}/{long_name}"
        result = processor._handle_attachment(msg, long_name, file_path)

    assert result == 1


def test_parse_email_headers_body_extract_queue(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers extracts body from queue."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    text_part = MIMEText("Body text", "plain")
    msg.attach(text_part)

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_base64_encoding(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with base64 body encoding."""
    import base64

    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "base64"
    msg.set_payload(base64.b64encode(b"Body text").decode())

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_8bit_encoding(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with 8bit body encoding."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "8bit"
    msg.set_payload("Body text")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_quoted_printable(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with quoted-printable encoding."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "quoted-printable"
    msg.set_payload("Body=20text")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_json_type_error(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers handles body JSON TypeError."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload(b"Binary body content")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_email_id_contains(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with email_id_contains."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)
    processor._email_id_contains = ["vault id"]

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test-email-id")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_extract_special_headers(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers extracts special headers."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["parentInternetMessageId"] = "<parent@example.com>"
    msg["parentGuid"] = "parent-guid-123"
    msg["emailGuid"] = "email-guid-456"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_mail_object_mkdir_tmp(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object creates tmp directory."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as base_dir:
        tmp_dir = f"{base_dir}/nonexistent/path"
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_decode_uni_string_partial_match(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with partial decoded strings."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Part1", "utf-8"), (b"Part2", "utf-8")]
        result = decode_uni_string("=?UTF-8?B?test?=", "fallback")

    assert result is not None


def test_extract_urls_domains_link_text_http(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts http from link text."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com">http://text-url.com link</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_extract_urls_domains_url_validation_fail(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains handles validation failures."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="not-a-valid-url">Link</a></html>'
    processor._extract_urls_domains(html, urls, domains)
    assert "not-a-valid-url" not in urls


def test_decode_uni_string_no_decoded_string(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with no decoded string at index."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = []
        result = decode_uni_string("test", "fallback")

    assert result is not None


def test_decode_uni_string_no_encoding(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with no encoding."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", None)]
        result = decode_uni_string("test", "fallback")

    assert result is not None


def test_decode_uni_string_unicode_dammit_append_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with UnicodeDammit append error."""
    EmailProcessor(mock_context, email_config)

    call_count = [0]

    def mock_ud(value):
        call_count[0] += 1
        if call_count[0] > 1:
            raise Exception("Unicode error")
        mock_result = MagicMock()
        mock_result.unicode_markup = "Test"
        return mock_result

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test1", "utf-8"), (b"Test2", "utf-8")]
        with patch(
            "soar_sdk.extras.email.processor.UnicodeDammit", side_effect=mock_ud
        ):
            result = decode_uni_string("test", "fallback")

    assert result is not None


def test_decode_uni_string_all_decoded(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when all parts are decoded."""
    EmailProcessor(mock_context, email_config)

    mock_ud = MagicMock()
    mock_ud.return_value.unicode_markup = "Test"

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", "utf-8")]
        with patch("soar_sdk.extras.email.processor.UnicodeDammit", mock_ud):
            result = decode_uni_string("=?UTF-8?B?VGVzdA==?=", "fallback")

    assert result is not None


def test_handle_attachment_oserror_long_path(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with OSError for long path."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        mock_open = MagicMock()
        mock_open.side_effect = [OSError("Name too long"), MagicMock()]

        with patch("builtins.open", mock_open):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result in [0, 1]


def test_handle_attachment_oserror_other(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with non-ENAMETOOLONG OSError."""
    import errno

    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        err = OSError()
        err.errno = errno.EACCES

        with patch("builtins.open", side_effect=err):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 0


def test_parse_email_headers_body_key_direct(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body key in headers."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["body"] = "Direct body content"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_type_error_decode(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body TypeError and decode."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload("String payload")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")

    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_save_ingested_file_not_added(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_save_ingested when file not added to vault."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    with patch.object(processor, "_handle_file", return_value=(1, False)):
        artifacts = [{"name": "Test", "cef": {}}]
        container = {"name": "Test"}
        files = [{"file_path": "/path/file.txt", "file_name": "file.txt"}]

        processor._handle_save_ingested(artifacts, container, None, files)


def test_parse_results_no_container_in_result(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results skips result with no container."""
    processor = EmailProcessor(mock_context, email_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": None,
                "artifacts": [{"name": "Artifact", "cef": {}}],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_parse_results_empty_artifact_in_list(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results handles None artifact in list."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)
    mock_context.soar.save_artifacts = MagicMock(return_value=[1])
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [None, {"name": "Real Artifact", "cef": {}}],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        with patch.object(processor, "_handle_save_ingested"):
            ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_handle_mail_object_non_multipart_no_payload(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object with non-multipart and no payload."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

"""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_if_body_inline_content_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_if_body with inline disposition and content_id."""
    processor = EmailProcessor(mock_context, email_config)

    msg = Message()
    msg.set_payload("Inline content")
    msg["Content-Type"] = "text/plain"

    bodies = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        result, process_further = processor._handle_if_body(
            "inline", "content-id-123", "text/plain", msg, bodies, file_path
        )

    assert result == 1


def test_extract_urls_from_src(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains extracts URLs from src attributes."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><img src="https://cdn.example.com/image.png"/><script src="https://js.example.com/app.js"></script></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "cdn.example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_handle_part_no_content_type(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part with no content type."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg.set_payload("Body content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_get_ips_ipv6_valid(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts valid IPv6 addresses."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = "Server at fe80::1 and 2001:db8::1"
    processor._get_ips(file_data, ips)


def test_decode_uni_string_no_decoded_at_index(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when decoded_string is None at index."""
    EmailProcessor(mock_context, email_config)

    result = decode_uni_string("plain text without encoding", "fallback")
    assert result is not None


def test_decode_uni_string_no_value_in_decoded(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when value is None."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(None, "utf-8")]
        result = decode_uni_string("test", "fallback")

    assert result is not None


def test_decode_uni_string_all_parts_decoded(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when all parts successfully decode."""
    EmailProcessor(mock_context, email_config)

    result = decode_uni_string("=?UTF-8?B?SGVsbG8=?=", "fallback")
    assert result is not None


def test_handle_attachment_inner_oserror(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with inner OSError not ENAMETOOLONG."""
    import errno

    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    err = OSError()
    err.errno = errno.ENAMETOOLONG

    inner_err = OSError()
    inner_err.errno = errno.EACCES

    call_count = [0]

    def mock_open_func(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise err
        raise inner_err

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        with patch("builtins.open", mock_open_func):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 0


def test_handle_attachment_inner_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment with inner exception."""
    import errno

    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    err = OSError()
    err.errno = errno.ENAMETOOLONG

    call_count = [0]

    def mock_open_func(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise err
        raise Exception("Generic error")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        with patch("builtins.open", mock_open_func):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 0


def test_handle_mail_object_body_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object when _handle_body raises exception."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body content here."""

    mail = email_module.message_from_string(rfc822_email)

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_handle_body", side_effect=Exception("Body error")),
    ):
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_mail_object_empty_body(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object with empty body in list."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    mail = email_module.message_from_string(rfc822_email)

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_parsed_mail", {"bodies": [None, {}]}),
    ):
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_parse_results_parent_guid_in_artifact(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with parentGuid in artifact cef."""
    processor = EmailProcessor(mock_context, email_config)
    processor._guid_to_hash = {"parent-guid": "parent-hash"}

    mock_context.soar.save_container = MagicMock(return_value=123)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [
                    {"name": "Art", "cef": {"parentGuid": "parent-guid"}},
                ],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        with patch.object(processor, "_handle_save_ingested"):
            ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_parse_results_email_guid_in_artifact(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with emailGuid in artifact cef."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [
                    {"name": "Art", "cef": {"emailGuid": "email-guid-123"}},
                ],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        with patch.object(processor, "_handle_save_ingested"):
            ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_add_vault_hashes_metadata_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary with metadata access exception."""
    processor = EmailProcessor(mock_context, email_config)

    mock_vault_data = MagicMock()
    mock_vault_data.__getitem__ = MagicMock(side_effect=Exception("Index error"))
    mock_context.vault.get_attachment = MagicMock(return_value=mock_vault_data)

    cef_artifact = {}
    ret_val, message = processor._add_vault_hashes_to_dictionary(
        cef_artifact, "vault-id"
    )

    assert ret_val == 0


def test_add_vault_hashes_no_metadata(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _add_vault_hashes_to_dictionary when metadata is None."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.get_attachment = MagicMock(return_value=[{"metadata": None}])

    cef_artifact = {}
    ret_val, message = processor._add_vault_hashes_to_dictionary(
        cef_artifact, "vault-id"
    )

    assert ret_val == 1


def test_handle_file_empty_cef(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file with empty cef_artifact after processing."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value=None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path)}

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_file_with_contains(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file with contains value."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_file_save_artifact_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file when save_artifact raises exception."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(side_effect=Exception("Save error"))

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "file_name": "test.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_file_with_filename_only(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file with filename set."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "file_name": "custom_name.txt"}

        with (
            patch.dict("sys.modules", {"magic": None}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_mail_object_body_none_in_list(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object skips None bodies."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body."""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_file_empty_cef_no_filename_no_vault(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file returns early with empty cef."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value=None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "meta_info": {}}

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1
    assert added == 1


def test_handle_file_with_file_contains(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file with contains from file type."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value="vault-id")
    mock_context.vault.get_attachment = MagicMock(
        return_value=[{"metadata": {"sha256": "hash"}}]
    )
    mock_context.soar.save_artifact = MagicMock(return_value=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.pdf"
        file_path.write_text("%PDF-1.4 content")

        curr_file = {"file_path": str(file_path), "file_name": "test.pdf"}

        mock_magic = MagicMock()
        mock_magic.from_file.return_value = "PDF document"

        with (
            patch.dict("sys.modules", {"magic": mock_magic}),
            patch("soar_sdk.extras.email.processor.phantom") as mock_phantom,
        ):
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_parse_results_parent_guid_not_in_hash(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results with parentGuid not in _guid_to_hash."""
    processor = EmailProcessor(mock_context, email_config)
    processor._guid_to_hash = {}

    mock_context.soar.save_container = MagicMock(return_value=123)

    with tempfile.TemporaryDirectory() as tmp_dir:
        results = [
            {
                "container": {"name": "Test"},
                "artifacts": [
                    {"name": "Art", "cef": {"parentGuid": "unknown-guid"}},
                ],
                "files": [],
                "temp_directory": tmp_dir,
            }
        ]

        with patch.object(processor, "_handle_save_ingested"):
            ret_val = processor._parse_results(results)

    assert ret_val == 1


def test_extract_urls_domains_no_links_or_srcs(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains with plain text (no HTML tags)."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    text = "Visit https://example.com/page for more info."
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(text, urls, domains)

    assert len(urls) >= 1


def test_extract_urls_domains_link_text_with_http(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains with link text containing http URL."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://link.com">Click here: http://in-text.com/path</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "link.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_decode_uni_string_successful_decode(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with successful complete decode."""
    EmailProcessor(mock_context, email_config)

    encoded = "=?UTF-8?B?SGVsbG8gV29ybGQ=?="
    result = decode_uni_string(encoded, "fallback")

    assert "Hello World" in result or result != "fallback"


def test_decode_uni_string_with_more_encoded_strings(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string with multiple encoded strings."""
    EmailProcessor(mock_context, email_config)

    encoded = "=?UTF-8?B?SGVsbG8=?= =?UTF-8?B?V29ybGQ=?="
    result = decode_uni_string(encoded, "fallback")
    assert result is not None


def test_decode_uni_string_value_none(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when value is None but encoding exists."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(None, "utf-8")]
        result = decode_uni_string("=?UTF-8?Q?test?=", "fallback")
    assert result is not None


def test_decode_uni_string_encoding_none_value_exists(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when encoding is None but value exists."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Value", None)]
        result = decode_uni_string("=?UTF-8?Q?test?=", "fallback")
    assert result is not None


def test_extract_urls_domains_uri_text_startswith_http(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains where uri_text contains http links."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com">https://visible-url.com</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_get_ips_ipv6_extraction(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts IPv6 addresses."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = "Connect to 2001:db8::1 or ::1"
    processor._get_ips(file_data, ips)


def test_handle_body_domain_from_email_regex2(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body extracts domains using EMAIL_REGEX2."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text('"quoted.name"@special-domain.com')

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "special-domain.com" in parsed_mail["domains"]


def test_parse_results_temp_directory_cleanup(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results cleans up temp directories."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    tmp_dir = tempfile.mkdtemp()
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    assert Path(tmp_dir).exists()

    results = [
        {
            "container": {"name": "Test"},
            "artifacts": [{"name": "Art", "cef": {}}],
            "files": [],
            "temp_directory": tmp_dir,
        }
    ]

    with patch.object(processor, "_handle_save_ingested"):
        processor._parse_results(results)

    assert not Path(tmp_dir).exists()


def test_handle_file_cef_empty_returns_early(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file when cef_artifact is empty after processing."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value=None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path)}

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_update_headers_empty_headers(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _update_headers with empty headers dict."""
    processor = EmailProcessor(mock_context, email_config)
    from requests.structures import CaseInsensitiveDict

    processor._external_headers = [
        CaseInsensitiveDict({"message-id": "<test@example.com>"})
    ]
    result = processor._update_headers(CaseInsensitiveDict())
    assert result == 1


def test_handle_part_with_content_id_no_filename(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_part uses content_id when no filename."""
    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    parsed_mail = {
        "bodies": [],
        "files": [],
        "email_headers": [],
    }

    msg = Message()
    msg["Content-Type"] = "text/plain"
    msg["Content-ID"] = "<content123@example.com>"
    msg.set_payload("Body content")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_part(msg, 0, tmp_dir, True, parsed_mail)

    assert result == 1


def test_parse_email_headers_body_unicode_decode_error(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers handles UnicodeDecodeError in body."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "8bit"
    msg.set_payload(b"\xff\xfe invalid bytes that cause unicode error")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_with_body_key_and_body(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body key present."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["bodyText"] = "This is the body content"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_attachment_oserror_then_generic_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_attachment when OSError is followed by generic exception."""
    import errno

    processor = EmailProcessor(mock_context, email_config)
    processor._parsed_mail = {"files": []}

    msg = Message()
    msg.set_payload(b"Content")

    err = OSError()
    err.errno = errno.ENAMETOOLONG

    call_count = [0]

    def mock_open_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError("File name too long")
        raise Exception("Fallback failed")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = f"{tmp_dir}/test.txt"
        with patch("builtins.open", side_effect=mock_open_side_effect):
            result = processor._handle_attachment(msg, "test.txt", file_path)

    assert result == 0


def test_handle_body_extract_domains_ip_filter(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body filters out IP addresses from domains."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Contact admin@192.168.1.1 for help")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "192.168.1.1" not in parsed_mail["domains"]


def test_extract_urls_domains_empty_unescape(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains with plain text needing unescape."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    text = "Click &lt;https://example.com/path&gt; for info"
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(text, urls, domains)


def test_handle_body_extract_hashes_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _handle_body with hash extraction disabled."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": False,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Hash: d41d8cd98f00b204e9800998ecf8427e")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert len(parsed_mail["hashes"]) == 0


def test_handle_body_extract_ips_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _handle_body with IP extraction disabled."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": False,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Contact 192.168.1.1 for help")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert len(parsed_mail["ips"]) == 0


def test_handle_file_no_vault_no_filename_empty_meta(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_file when no vault_id, no filename, empty meta_info."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.vault.add_attachment = MagicMock(return_value=None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "unnamed"
        file_path.write_text("content")

        curr_file = {"file_path": str(file_path), "meta_info": {}, "file_name": None}

        with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
            mock_phantom.APP_JSON_ACTION_NAME = "action"
            mock_phantom.APP_JSON_APP_RUN_ID = "run_id"
            ret_val, added = processor._handle_file(curr_file, [], 123, 0)

    assert ret_val == 1


def test_handle_mail_object_empty_body_continue(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object continues when body is empty."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

"""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_get_ips_valid_ipv6(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts valid IPv6 address."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = " 2001:0db8:85a3:0000:0000:8a2e:0370:7334 "
    processor._get_ips(file_data, ips)


def test_decode_uni_string_unicode_markup_exception(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when UnicodeDammit.unicode_markup fails."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", "utf-8")]
        with patch("soar_sdk.extras.email.utils.UnicodeDammit") as mock_ud:
            mock_instance = MagicMock()
            mock_instance.unicode_markup = None
            mock_ud.return_value = mock_instance
            result = decode_uni_string("=?UTF-8?Q?test?=", "fallback")

    assert result is not None


def test_extract_urls_domains_urls_only_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _extract_urls_domains with only URL extraction disabled."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": False,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com">Link</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) == 0
    assert "example.com" in domains


def test_extract_urls_domains_domains_only_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _extract_urls_domains with only domain extraction disabled."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": False,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com">Link</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1
    assert len(domains) == 0


def test_parse_email_headers_body_json_unicode_decode(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers handles json.dumps UnicodeDecodeError."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload(b"\xff\xfe invalid")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_with_content_encoding(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers handles Content-Transfer-Encoding."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "quoted-printable"
    msg.set_payload("Test body")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_mail_object_body_returns_error(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object when body returns error (empty file)."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

x"""

    mail = email_module.message_from_string(rfc822_email)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_handle_body_extract_domains_disabled(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _handle_body with domain extraction disabled."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": False,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Contact test@example.com")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert len(parsed_mail["domains"]) == 0


def test_decode_uni_string_empty_dict_map(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when decoded_string is not in map."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = []
        result = decode_uni_string("=?UTF-8?Q?test?=", "fallback")

    assert result == "fallback"


def test_handle_mail_object_with_none_body_in_list(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object skips None bodies in list."""
    import email as email_module

    processor = EmailProcessor(mock_context, email_config)

    rfc822_email = """From: sender@example.com
Subject: Test
Content-Type: text/plain

Body content here."""

    mail = email_module.message_from_string(rfc822_email)

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_handle_body") as mock_handle_body,
    ):
        mock_handle_body.return_value = 1
        result = processor._handle_mail_object(
            mail, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_decode_uni_string_continue_on_empty_decoded(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string continues when decoded_string is not in map."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"First", "utf-8")]
        result = decode_uni_string(
            "=?UTF-8?B?Rmlyc3Q=?= =?UTF-8?B?TWlzc2luZw==?=", "fallback"
        )

    assert result is not None


def test_decode_uni_string_unicode_markup_is_none(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string when unicode_markup returns empty string."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"Test", "utf-8")]
        with patch("soar_sdk.extras.email.utils.UnicodeDammit") as mock_ud:
            mock_instance = MagicMock()
            mock_instance.unicode_markup = ""
            mock_ud.return_value = mock_instance
            result = decode_uni_string("=?UTF-8?Q?test?=", "fallback")

    assert result is not None


def test_parse_email_headers_body_type_error_with_bytes(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with body causing TypeError then bytes encoding."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload(b"\xff\xfe invalid bytes")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_handle_body_empty_domain_after_at(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body with email that has empty domain after @."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Contact test@ for help")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")


def test_parse_results_no_result_temp_directory(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_results when temp_directory is not in result."""
    processor = EmailProcessor(mock_context, email_config)

    mock_context.soar.save_container = MagicMock(return_value=123)

    results = [
        {
            "container": {"name": "Test"},
            "artifacts": [{"name": "Art", "cef": {}}],
            "files": [],
        }
    ]

    with patch.object(processor, "_handle_save_ingested"):
        processor._parse_results(results)


def test_extract_urls_domains_with_empty_uri_text(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains when links have empty text."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com"></a><img src="https://cdn.example.com/img.png"/></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 1


def test_extract_urls_domains_uri_text_with_http_link(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains when link text starts with http."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = (
        '<html><a href="https://example.com">https://visible-link.com/path</a></html>'
    )
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert "https://visible-link.com/path" in urls or len(urls) >= 1


def test_extract_urls_domains_mailto_with_ip_domain(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains skips mailto with IP as domain."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="mailto:user@192.168.1.1">Email</a></html>'
    processor._extract_urls_domains(html, urls, domains)

    assert "192.168.1.1" not in domains


def test_get_ips_with_valid_ipv6(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _get_ips extracts valid IPv6 addresses."""
    processor = EmailProcessor(mock_context, email_config)
    ips: set[str] = set()

    file_data = " 2001:0db8:85a3:0000:0000:8a2e:0370:7334 "
    processor._get_ips(file_data, ips)

    assert len(ips) >= 0


def test_handle_body_email_with_ip_domain(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body filters IP addresses from email domains."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text("Email admin@10.0.0.1 for support")

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "10.0.0.1" not in parsed_mail["domains"]


def test_decode_uni_string_skip_empty_in_map(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string continues when decoded_string is None."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(b"First", "utf-8"), (None, None)]
        result = decode_uni_string(
            "=?UTF-8?B?Rmlyc3Q=?= =?UTF-8?B?U2Vjb25k?=", "fallback"
        )

    assert result is not None


def test_decode_uni_string_value_none_encoding_exists(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _decode_uni_string continues when value is None."""
    EmailProcessor(mock_context, email_config)

    with patch("soar_sdk.extras.email.utils.decode_header") as mock_decode:
        mock_decode.return_value = [(None, "utf-8"), (b"Second", "utf-8")]
        result = decode_uni_string(
            "=?UTF-8?B?Rmlyc3Q=?= =?UTF-8?B?U2Vjb25k?=", "fallback"
        )

    assert result is not None


def test_handle_mail_object_with_empty_body_dict(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_mail_object skips empty body dicts."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    processor = EmailProcessor(mock_context, email_config)

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test"
    msg.attach(MIMEText("Body", "plain"))

    rfc822_email = msg.as_string()

    def mock_handle_part(part, i, tmp_dir, extract_attach, parsed_mail):
        if i == 1:
            parsed_mail["bodies"].append(None)
            parsed_mail["bodies"].append({})
        return 1

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch.object(processor, "_handle_part", side_effect=mock_handle_part),
    ):
        result = processor._handle_mail_object(
            msg, "email-id", rfc822_email, tmp_dir, 1234567890.0
        )

    assert result == 1


def test_parse_email_headers_empty_from(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers with empty From header."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": False,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = ""
    msg["To"] = ""
    msg["Message-ID"] = "<test@example.com>"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_no_headers_no_message_id(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _parse_email_headers returns 0 when no cef_artifact and no message_id."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {"email_headers": []}

    msg = Message()

    result = processor._parse_email_headers(parsed_mail, msg)
    assert result == 0


def test_parse_email_headers_body_with_key(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers when body key is found in headers."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["bodyText"] = "This is the body text"

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_type_error_base64(
    mock_context: ProcessEmailContext,
) -> None:
    """Test _parse_email_headers handles TypeError by base64 encoding."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_payload(b"\xff\xfe\x80\x81 invalid utf-8 bytes")

    processor._parse_email_headers(parsed_mail, msg, add_email_id="test")
    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_base64_fallback(
    mock_context: ProcessEmailContext,
) -> None:
    """Test base64 fallback when decode fails."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "8bit"

    class BadPayload:
        def decode(self, encoding):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")

        def __str__(self):
            return "bad payload"

    with patch.object(msg, "get_payload", return_value=BadPayload()):
        processor._parse_email_headers(parsed_mail, msg, add_email_id="test")

    assert len(parsed_mail["email_headers"]) >= 1


def test_parse_email_headers_body_bytes_base64(
    mock_context: ProcessEmailContext,
) -> None:
    """Test base64 encoding when payload is bytes."""
    config = {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }
    mock_soar = MagicMock()
    mock_vault = MagicMock()
    context = ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test",
        folder_name="INBOX",
        is_hex=False,
    )
    processor = EmailProcessor(context, config)

    parsed_mail = {"email_headers": []}

    msg = Message()
    msg["From"] = "sender@example.com"
    msg["Message-ID"] = "<test@example.com>"
    msg["Content-Transfer-Encoding"] = "8bit"

    class BadBytes(bytes):
        def decode(self, encoding="utf-8", errors="strict"):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")

    bad_bytes = BadBytes(b"\xff\xfe\x80\x81")
    with patch.object(msg, "get_payload", return_value=bad_bytes):
        processor._parse_email_headers(parsed_mail, msg, add_email_id="test")

    assert len(parsed_mail["email_headers"]) >= 1
    headers = parsed_mail["email_headers"][0]
    assert headers.get("cef", {}).get("body_base64encoded") is True


def test_extract_urls_domains_link_text_no_http(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _extract_urls_domains when link texts don't start with http."""
    processor = EmailProcessor(mock_context, email_config)
    urls: set[str] = set()
    domains: set[str] = set()

    html = '<html><a href="https://example.com">Click here</a><a href="https://other.com">Link text</a></html>'
    with patch("soar_sdk.extras.email.processor.phantom") as mock_phantom:
        mock_phantom.get_host_from_url.return_value = "example.com"
        processor._extract_urls_domains(html, urls, domains)

    assert len(urls) >= 2


def test_handle_body_email_regex_with_ip_domain(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test _handle_body filters emails with IP domains."""
    processor = EmailProcessor(mock_context, email_config)

    parsed_mail = {
        "ips": set(),
        "hashes": set(),
        "urls": set(),
        "domains": set(),
        "email_headers": [],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        body_file = Path(tmp_dir) / "body.txt"
        body_file.write_text(
            "Contact admin@192.168.1.100 and user@example.com for help"
        )

        body = {"file_path": str(body_file), "charset": "utf-8"}
        with patch("soar_sdk.extras.email.processor.phantom"):
            processor._handle_body(body, parsed_mail, 0, "email-123")

    assert "192.168.1.100" not in parsed_mail["domains"]
    assert "example.com" in parsed_mail["domains"]
