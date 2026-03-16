"""Outlook .msg email parsing using the extract-msg library."""

from __future__ import annotations

from typing import Any, cast

from extract_msg import Message

from soar_sdk.extras.email.base import (
    EmailAttachment,
    EmailBody,
    EmailData,
    EmailHeaders,
    _extract_urls_from_content,
)
from soar_sdk.logging import getLogger

logger = getLogger()

# Backward-compatible alias
OutlookEmailData = EmailData


def _extract_outlook_headers(
    msg: Message,
    email_id: str | None = None,
) -> EmailHeaders:
    """Extract headers from a parsed Outlook Message."""
    headers = EmailHeaders()
    headers.email_id = email_id
    headers.message_id = msg.messageId
    headers.to = msg.to
    headers.from_address = msg.sender
    headers.subject = msg.subject
    headers.date = str(msg.date) if msg.date is not None else None
    headers.cc = msg.cc
    headers.bcc = msg.bcc
    headers.reply_to = None
    headers.content_type = None

    header_dict: dict[str, Any] = msg.headerDict or {}

    x_mailer = header_dict.get("X-Mailer")
    headers.x_mailer = x_mailer if isinstance(x_mailer, str) else None

    x_priority = header_dict.get("X-Priority")
    headers.x_priority = x_priority if isinstance(x_priority, str) else None

    reply_to = header_dict.get("Reply-To")
    headers.reply_to = reply_to if isinstance(reply_to, str) else None

    content_type = header_dict.get("Content-Type")
    headers.content_type = content_type if isinstance(content_type, str) else None

    received_raw = header_dict.get("Received")
    if isinstance(received_raw, list):
        headers.received = [str(r) for r in received_raw]
    elif isinstance(received_raw, str):
        headers.received = [received_raw]

    for key, value in header_dict.items():
        if key.lower() == "received":
            continue
        headers.raw_headers[key] = str(value) if value is not None else None

    return headers


def _extract_outlook_body(msg: Message) -> EmailBody:
    """Extract plain text and HTML body from an Outlook Message."""
    body = EmailBody()

    plain_text = msg.body
    if plain_text and isinstance(plain_text, str):
        body.plain_text = plain_text

    html_body = msg.htmlBody
    if html_body:
        if isinstance(html_body, bytes):
            body.html = html_body.decode("utf-8", errors="replace")
        elif isinstance(html_body, str):
            body.html = html_body

    return body


def _extract_outlook_urls(msg: Message) -> list[str]:
    """Extract all URLs from Outlook email body content."""
    urls: set[str] = set()
    body = _extract_outlook_body(msg)

    if body.html:
        _extract_urls_from_content(body.html, urls, is_html=True)
    if body.plain_text:
        _extract_urls_from_content(body.plain_text, urls, is_html=False)

    return sorted(urls)


def _extract_outlook_attachments(
    msg: Message,
    include_content: bool = False,
) -> list[EmailAttachment]:
    """Extract attachment metadata from an Outlook Message."""
    attachments: list[EmailAttachment] = []

    for att in msg.attachments:
        filename = att.name or "unnamed_attachment"
        content_id = att.cid if isinstance(att.cid, str) else None
        data = att.data if isinstance(att.data, bytes) else None

        attachment = EmailAttachment(
            filename=filename,
            content_type=att.mimetype,
            size=len(data) if data else 0,
            content_id=content_id.strip("<>") if content_id else None,
            is_inline=bool(content_id),
        )

        if include_content and data:
            attachment.content = data

        attachments.append(attachment)

    return attachments


def extract_outlook_email_data(
    msg_bytes: bytes,
    email_id: str | None = None,
    include_attachment_content: bool = False,
) -> EmailData:
    """Extract all components from an Outlook .msg email.

    Args:
        msg_bytes: Raw bytes of the .msg file.
        email_id: Optional identifier for the email.
        include_attachment_content: Whether to include raw attachment bytes.

    Returns:
        An EmailData instance with extracted headers, body, URLs,
        and attachments.

    """
    import extract_msg

    msg = cast(Message, extract_msg.openMsg(msg_bytes))

    try:
        return EmailData(
            raw_email=msg_bytes,
            headers=_extract_outlook_headers(msg, email_id),
            body=_extract_outlook_body(msg),
            urls=_extract_outlook_urls(msg),
            attachments=_extract_outlook_attachments(msg, include_attachment_content),
        )
    finally:
        msg.close()
