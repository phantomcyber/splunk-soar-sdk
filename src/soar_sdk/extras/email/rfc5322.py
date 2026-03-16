"""RFC 5322 (.eml) email parsing."""

import email
from email.header import decode_header, make_header
from email.message import Message

from bs4 import UnicodeDammit  # type: ignore[attr-defined]

from soar_sdk.extras.email.base import (
    EmailAttachment,
    EmailBody,
    EmailData,
    EmailHeaders,
    _extract_urls_from_content,
    extract_domains_from_urls,
    extract_email_addresses,
    extract_urls_from_body,
)
from soar_sdk.extras.email.utils import decode_uni_string
from soar_sdk.logging import getLogger

logger = getLogger()

# Backward-compatible alias
RFC5322EmailData = EmailData


def extract_email_addresses_from_body(mail: Message) -> list[str]:
    """Extract email addresses found in the email body.

    Backward-compatible wrapper that accepts an RFC 5322 Message.
    """
    body = extract_email_body(mail)
    return extract_email_addresses(body)


# Re-export base classes and shared functions for backward compatibility
__all__ = [
    "EmailAttachment",
    "EmailBody",
    "EmailHeaders",
    "RFC5322EmailData",
    "_decode_header_value",
    "_decode_payload",
    "_extract_urls_from_content",
    "extract_domains_from_urls",
    "extract_email_addresses_from_body",
    "extract_email_attachments",
    "extract_email_body",
    "extract_email_headers",
    "extract_email_urls",
    "extract_rfc5322_email_data",
]


# --- RFC 5322-specific helpers ---


def _decode_header_value(value: str | None) -> str | None:
    """Decode an RFC 2047 encoded header value."""
    if not value:
        return None
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return decode_uni_string(value, value)


def _get_charset(part: Message) -> str:
    """Get the charset from an email message part."""
    charset = part.get_content_charset()
    return charset if charset else "utf-8"


def _decode_payload(payload: bytes, charset: str) -> str:
    """Decode email payload bytes with fallback handling."""
    try:
        return UnicodeDammit(payload).unicode_markup.encode("utf-8").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            return payload.decode(charset)
        except UnicodeDecodeError:
            return payload.decode("utf-8", errors="replace")


# --- RFC 5322-specific extraction functions ---


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
    body = extract_email_body(mail)
    return extract_urls_from_body(body)


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
) -> EmailData:
    """Extract all components from an RFC 5322 email string."""
    mail = email.message_from_string(rfc822_email)

    return EmailData(
        raw_email=rfc822_email,
        headers=extract_email_headers(mail, email_id),
        body=extract_email_body(mail),
        urls=extract_email_urls(mail),
        attachments=extract_email_attachments(mail, include_attachment_content),
    )
