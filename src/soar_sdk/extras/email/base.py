"""Base email data classes, shared extraction helpers, and auto-detection."""

import base64
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from soar_sdk.extras.email.utils import clean_url, is_ip
from soar_sdk.logging import getLogger

logger = getLogger()

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0"

URI_REGEX = r"[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMAIL_REGEX = r"\b[A-Z0-9._%+-]+@+[A-Z0-9.-]+\.[A-Z]{2,}\b"


@dataclass
class EmailHeaders:
    """Extracted email headers from an email message."""

    email_id: str | None = None
    message_id: str | None = None
    to: str | None = None
    from_address: str | None = None
    subject: str | None = None
    date: str | None = None
    received: list[str] = field(default_factory=list)
    cc: str | None = None
    bcc: str | None = None
    x_mailer: str | None = None
    x_priority: str | None = None
    reply_to: str | None = None
    content_type: str | None = None
    raw_headers: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailBody:
    """Extracted email body content."""

    plain_text: str | None = None
    html: str | None = None
    charset: str | None = None


@dataclass
class EmailAttachment:
    """Extracted email attachment metadata."""

    filename: str
    content_type: str | None = None
    size: int = 0
    content_id: str | None = None
    content: bytes | None = None
    is_inline: bool = False


@dataclass
class EmailData:
    """Complete extracted data from an email message."""

    raw_email: str | bytes
    headers: EmailHeaders
    body: EmailBody
    urls: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        raw = self.raw_email
        if isinstance(raw, bytes):
            raw = base64.b64encode(raw).decode("ascii")

        return {
            "raw_email": raw,
            "headers": {
                "email_id": self.headers.email_id,
                "message_id": self.headers.message_id,
                "to": self.headers.to,
                "from": self.headers.from_address,
                "subject": self.headers.subject,
                "date": self.headers.date,
                "received": self.headers.received,
                "cc": self.headers.cc,
                "bcc": self.headers.bcc,
                "x_mailer": self.headers.x_mailer,
                "x_priority": self.headers.x_priority,
                "reply_to": self.headers.reply_to,
                "content_type": self.headers.content_type,
                "raw_headers": self.headers.raw_headers,
            },
            "body": {
                "plain_text": self.body.plain_text,
                "html": self.body.html,
                "charset": self.body.charset,
            },
            "urls": self.urls,
            "attachments": [
                {
                    "filename": att.filename,
                    "content_type": att.content_type,
                    "size": att.size,
                    "content_id": att.content_id,
                    "is_inline": att.is_inline,
                }
                for att in self.attachments
            ],
        }


# --- Shared extraction helpers ---


def _extract_urls_from_content(content: str, urls: set[str], is_html: bool) -> None:
    """Extract URLs from HTML or plain text content."""
    if is_html:
        try:
            soup = BeautifulSoup(content, "html.parser")
            for link in soup.find_all(href=True):
                href = link["href"]
                if href and not href.startswith("mailto:"):
                    cleaned = clean_url(href)
                    if cleaned.startswith("http"):
                        urls.add(cleaned)
            for src in soup.find_all(src=True):
                src_val = src["src"]
                if src_val:
                    cleaned = clean_url(src_val)
                    if cleaned.startswith("http"):
                        urls.add(cleaned)
        except Exception as e:
            logger.debug(f"Error parsing HTML for URLs: {e}")

    content = unescape(content)
    uri_matches = re.findall(URI_REGEX, content)
    for uri in uri_matches:
        urls.add(clean_url(uri))


def extract_urls_from_body(body: EmailBody) -> list[str]:
    """Extract all URLs from an EmailBody's content."""
    urls: set[str] = set()

    if body.html:
        _extract_urls_from_content(body.html, urls, is_html=True)
    if body.plain_text:
        _extract_urls_from_content(body.plain_text, urls, is_html=False)

    return sorted(urls)


def extract_domains_from_urls(urls: list[str]) -> list[str]:
    """Extract unique domains from a list of URLs."""
    domains: set[str] = set()

    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.netloc and not is_ip(parsed.netloc):
                domain = parsed.netloc.split(":")[0]
                domains.add(domain)
        except Exception as e:
            logger.debug(f"Failed to parse URL for domain extraction: {e}")
            continue

    return sorted(domains)


def extract_email_addresses(body: EmailBody) -> list[str]:
    """Extract email addresses found in an EmailBody's content."""
    addresses: set[str] = set()

    content = ""
    if body.plain_text:
        content += body.plain_text
    if body.html:
        content += body.html

    if content:
        matches = re.findall(EMAIL_REGEX, content, re.IGNORECASE)
        addresses.update(m.lower() for m in matches)

    return sorted(addresses)


# --- Format auto-detection ---


def _is_msg_bytes(data: bytes) -> bool:
    """Check if bytes represent an OLE2 compound file (.msg format)."""
    return data[:4] == _OLE2_MAGIC


def extract_email_data(
    email_input: str | bytes | Path,
    email_id: str | None = None,
    include_attachment_content: bool = False,
) -> EmailData:
    """Auto-detect email format and extract data.

    Args:
        email_input: Raw email content as string (RFC 5322), bytes (.msg or .eml),
            or a Path to an email file.
        email_id: Optional identifier for the email.
        include_attachment_content: Whether to include raw attachment bytes.

    Returns:
        An EmailData instance with extracted headers, body, URLs, and attachments.

    Raises:
        TypeError: If email_input is not str, bytes, or Path.
        ValueError: If the email format cannot be determined.

    """
    if isinstance(email_input, Path):
        return _extract_from_path(email_input, email_id, include_attachment_content)

    if isinstance(email_input, bytes):
        return _extract_from_bytes(email_input, email_id, include_attachment_content)

    if isinstance(email_input, str):
        return _extract_from_str(email_input, email_id, include_attachment_content)

    msg = f"Unsupported email_input type: {type(email_input)}"
    raise TypeError(msg)


def _extract_from_path(
    path: Path,
    email_id: str | None,
    include_attachment_content: bool,
) -> EmailData:
    """Extract email data from a file path."""
    suffix = path.suffix.lower()
    raw_bytes = path.read_bytes()

    if suffix == ".msg":
        from soar_sdk.extras.email.outlook import extract_outlook_email_data

        return extract_outlook_email_data(
            raw_bytes, email_id, include_attachment_content
        )

    if suffix == ".eml":
        from soar_sdk.extras.email.rfc5322 import extract_rfc5322_email_data

        return extract_rfc5322_email_data(
            raw_bytes.decode("utf-8", errors="replace"),
            email_id,
            include_attachment_content,
        )

    msg = f"Unrecognized email file extension: {suffix}"
    raise ValueError(msg)


def _extract_from_bytes(
    data: bytes,
    email_id: str | None,
    include_attachment_content: bool,
) -> EmailData:
    """Extract email data from raw bytes, detecting format by magic bytes."""
    if _is_msg_bytes(data):
        from soar_sdk.extras.email.outlook import extract_outlook_email_data

        return extract_outlook_email_data(data, email_id, include_attachment_content)

    from soar_sdk.extras.email.rfc5322 import extract_rfc5322_email_data

    return extract_rfc5322_email_data(
        data.decode("utf-8", errors="replace"),
        email_id,
        include_attachment_content,
    )


def _extract_from_str(
    text: str,
    email_id: str | None,
    include_attachment_content: bool,
) -> EmailData:
    """Extract email data from a string (file path or raw RFC 5322 text)."""
    path = Path(text)
    if path.suffix.lower() in (".msg", ".eml") and path.exists():
        return _extract_from_path(path, email_id, include_attachment_content)

    from soar_sdk.extras.email.rfc5322 import extract_rfc5322_email_data

    return extract_rfc5322_email_data(text, email_id, include_attachment_content)
