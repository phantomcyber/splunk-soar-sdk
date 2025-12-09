import email
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.message import Message
from html import unescape
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, UnicodeDammit  # type: ignore[attr-defined]

from soar_sdk.extras.email.utils import clean_url, decode_uni_string, is_ip
from soar_sdk.logging import getLogger

logger = getLogger()

URI_REGEX = r"[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMAIL_REGEX = r"\b[A-Z0-9._%+-]+@+[A-Z0-9.-]+\.[A-Z]{2,}\b"


@dataclass
class EmailHeaders:
    """Extracted email headers from an RFC 5322 message."""

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
class RFC5322EmailData:
    """Complete extracted data from an RFC 5322 email message."""

    raw_email: str
    headers: EmailHeaders
    body: EmailBody
    urls: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "raw_email": self.raw_email,
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


def _decode_header_value(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return decode_uni_string(value, value)


def _get_charset(part: Message) -> str:
    charset = part.get_content_charset()
    return charset if charset else "utf-8"


def _decode_payload(payload: bytes, charset: str) -> str:
    try:
        return UnicodeDammit(payload).unicode_markup.encode("utf-8").decode("utf-8")
    except Exception:
        try:
            return payload.decode(charset)
        except Exception:
            return payload.decode("utf-8", errors="replace")


def _extract_urls_from_content(content: str, urls: set[str], is_html: bool) -> None:
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


def extract_email_headers(mail: Message, email_id: str | None = None) -> EmailHeaders:
    """Extract headers from a parsed email Message."""
    headers = EmailHeaders()
    headers.email_id = email_id
    headers.message_id = mail.get("Message-ID")
    headers.to = _decode_header_value(mail.get("To"))
    headers.from_address = _decode_header_value(mail.get("From"))
    headers.subject = _decode_header_value(mail.get("Subject"))
    headers.date = mail.get("Date")
    headers.cc = _decode_header_value(mail.get("CC"))
    headers.bcc = _decode_header_value(mail.get("BCC"))
    headers.x_mailer = mail.get("X-Mailer")
    headers.x_priority = mail.get("X-Priority")
    headers.reply_to = _decode_header_value(mail.get("Reply-To"))
    headers.content_type = mail.get("Content-Type")

    received_headers = mail.get_all("Received") or []
    headers.received = [str(r) for r in received_headers]

    for key, value in mail.items():
        if key.lower() == "received":
            continue
        headers.raw_headers[key] = _decode_header_value(str(value)) if value else None

    return headers


def extract_email_body(mail: Message) -> EmailBody:
    """Extract plain text and HTML body from a parsed email Message."""
    body = EmailBody()
    charset = _get_charset(mail)
    body.charset = charset

    if not mail.is_multipart():
        payload = mail.get_payload(decode=True)
        if payload and isinstance(payload, bytes):
            content_type = mail.get_content_type()
            decoded = _decode_payload(payload, charset)
            if content_type == "text/html":
                body.html = decoded
            else:
                body.plain_text = decoded
        return body

    for part in mail.walk():
        if part.is_multipart():
            continue

        content_type = part.get_content_type()
        content_disp = str(part.get("Content-Disposition") or "")

        if "attachment" in content_disp.lower():
            continue

        payload = part.get_payload(decode=True)
        if not payload or not isinstance(payload, bytes):
            continue

        part_charset = _get_charset(part)
        decoded = _decode_payload(payload, part_charset)

        if content_type == "text/plain" and not body.plain_text:
            body.plain_text = decoded
        elif content_type == "text/html" and not body.html:
            body.html = decoded

    return body


def extract_email_urls(mail: Message) -> list[str]:
    """Extract all URLs from email body content."""
    urls: set[str] = set()
    body = extract_email_body(mail)

    if body.html:
        _extract_urls_from_content(body.html, urls, is_html=True)
    if body.plain_text:
        _extract_urls_from_content(body.plain_text, urls, is_html=False)

    return sorted(urls)


def extract_email_attachments(
    mail: Message, include_content: bool = False
) -> list[EmailAttachment]:
    """Extract attachment metadata from a parsed email Message."""
    attachments: list[EmailAttachment] = []

    if not mail.is_multipart():
        return attachments

    for part in mail.walk():
        if part.is_multipart():
            continue

        content_disp = str(part.get("Content-Disposition") or "")
        content_type = part.get_content_type()
        content_id = part.get("Content-ID")

        filename = part.get_filename()
        if not filename:
            if "attachment" not in content_disp.lower():
                continue
            filename = "unnamed_attachment"

        filename = _decode_header_value(filename) or filename
        is_inline = "inline" in content_disp.lower()
        raw_payload = part.get_payload(decode=True)
        payload = raw_payload if isinstance(raw_payload, bytes) else None

        attachment = EmailAttachment(
            filename=filename,
            content_type=content_type,
            size=len(payload) if payload else 0,
            content_id=content_id.strip("<>") if content_id else None,
            is_inline=is_inline,
        )

        if include_content and payload:
            attachment.content = payload

        attachments.append(attachment)

    return attachments


def extract_rfc5322_email_data(
    rfc822_email: str,
    email_id: str | None = None,
    include_attachment_content: bool = False,
) -> RFC5322EmailData:
    """Extract all components from an RFC 5322 email string."""
    mail = email.message_from_string(rfc822_email)

    return RFC5322EmailData(
        raw_email=rfc822_email,
        headers=extract_email_headers(mail, email_id),
        body=extract_email_body(mail),
        urls=extract_email_urls(mail),
        attachments=extract_email_attachments(mail, include_attachment_content),
    )


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


def extract_email_addresses_from_body(mail: Message) -> list[str]:
    """Extract email addresses found in the email body."""
    addresses: set[str] = set()
    body = extract_email_body(mail)

    content = ""
    if body.plain_text:
        content += body.plain_text
    if body.html:
        content += body.html

    if content:
        matches = re.findall(EMAIL_REGEX, content, re.IGNORECASE)
        addresses.update(m.lower() for m in matches)

    return sorted(addresses)
