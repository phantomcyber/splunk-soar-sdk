"""Tests for email processing module."""

from unittest.mock import MagicMock

import pytest

from soar_sdk.extras.email import EmailProcessor, ProcessEmailContext


@pytest.fixture
def mock_context() -> ProcessEmailContext:
    """Create a mock email processing context."""
    mock_soar = MagicMock()
    mock_vault = MagicMock()

    return ProcessEmailContext(
        soar=mock_soar,
        vault=mock_vault,
        app_id="test-app-id",
        folder_name="INBOX",
        is_hex=False,
        action_name="test_action",
        app_run_id=123,
    )


@pytest.fixture
def email_config() -> dict[str, bool]:
    """Create default email processing configuration."""
    return {
        "extract_attachments": True,
        "add_body_to_header_artifacts": True,
        "extract_urls": True,
        "extract_ips": True,
        "extract_domains": True,
        "extract_hashes": True,
    }


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


def test_is_ipv4(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test IPv4 validation."""
    processor = EmailProcessor(mock_context, email_config)

    assert processor._is_ip("192.168.1.1")
    assert processor._is_ip("10.0.0.1")
    assert processor._is_ip("255.255.255.255")
    assert not processor._is_ip("256.1.1.1")
    assert not processor._is_ip("not.an.ip.address")


def test_is_ipv6(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test IPv6 validation."""
    processor = EmailProcessor(mock_context, email_config)

    assert processor.is_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert processor.is_ipv6("::1")
    assert processor.is_ipv6("fe80::1")
    assert not processor.is_ipv6("not-an-ipv6")
    assert not processor.is_ipv6("192.168.1.1")


def test_is_sha1(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test SHA1 hash validation."""
    processor = EmailProcessor(mock_context, email_config)

    assert processor._is_sha1("356a192b7913b04c54574d18c28d46e6395428ab")
    assert processor._is_sha1("da39a3ee5e6b4b0d3255bfef95601890afd80709")
    assert not processor._is_sha1("not-a-sha1-hash")
    assert not processor._is_sha1("356a192b")


def test_clean_url(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test URL cleaning."""
    processor = EmailProcessor(mock_context, email_config)

    assert processor._clean_url("https://example.com>") == "https://example.com"
    assert processor._clean_url("https://example.com<") == "https://example.com"
    assert processor._clean_url("https://example.com]") == "https://example.com"
    assert processor._clean_url("https://example.com,") == "https://example.com"
    assert processor._clean_url("https://example.com> ") == "https://example.com"


def test_decode_uni_string(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test unicode string decoding."""
    processor = EmailProcessor(mock_context, email_config)

    plain_string = "Hello World"
    assert processor._decode_uni_string(plain_string, "default") == plain_string

    encoded_string = "=?UTF-8?Q?Hello?= World"
    result = processor._decode_uni_string(encoded_string, "default")
    assert "Hello" in result


def test_get_container_name(
    mock_context: ProcessEmailContext, email_config: dict[str, bool]
) -> None:
    """Test container name extraction."""
    processor = EmailProcessor(mock_context, email_config)

    from collections import OrderedDict

    parsed_mail = OrderedDict()
    parsed_mail["subject"] = "Test Email Subject"

    container_name = processor._get_container_name(parsed_mail, "test-email-id-123")
    assert "Test Email Subject" in container_name

    parsed_mail_no_subject = OrderedDict()
    container_name_no_subject = processor._get_container_name(
        parsed_mail_no_subject, "test-email-id-456"
    )
    assert container_name_no_subject == "Email ID: test-email-id-456"
