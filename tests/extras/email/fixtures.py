"""Generated RFC 5322 fixtures for the email-ingestion safety contract."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser


@dataclass(frozen=True)
class AttachmentFixture:
    """One decoded leaf attachment to add to a generated message."""

    filename: str
    content: bytes
    maintype: str = "application"
    subtype: str = "octet-stream"


def make_email(
    *,
    subject: str = "Direct message",
    body: str = "Inspect https://suspicious.example/path",
    sender: str = "attacker@example.test",
    recipient: str = "analyst@example.test",
    attachments: Iterable[AttachmentFixture] = (),
) -> bytes:
    """Build a deterministic direct message with decoded leaf attachments."""
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = f"<{subject.lower().replace(' ', '-')}@example.test>"
    message.set_content(body)

    for attachment in attachments:
        message.add_attachment(
            attachment.content,
            maintype=attachment.maintype,
            subtype=attachment.subtype,
            filename=attachment.filename,
        )

    return message.as_bytes(policy=policy.SMTP)


def make_report_envelope(
    reported_messages: Iterable[tuple[str, bytes]],
    *,
    subject: str = "User-reported suspicious email",
) -> bytes:
    """Build a forwarding envelope with one or more attached RFC 5322 messages."""
    envelope = EmailMessage(policy=policy.SMTP)
    envelope["From"] = "reporter@example.test"
    envelope["To"] = "soc@example.test"
    envelope["Subject"] = subject
    envelope["Message-ID"] = "<report-envelope@example.test>"
    envelope.set_content("Please investigate the attached message.")

    for filename, raw_message in reported_messages:
        parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
        envelope.add_attachment(parsed, filename=filename)

    return envelope.as_bytes(policy=policy.SMTP)


def make_attachment_flood(count: int = 101, *, payload_size: int = 1) -> bytes:
    """Build a message with many small attachments without static binary fixtures."""
    attachments = [
        AttachmentFixture(
            f"attachment-{index:03d}.bin", bytes([index % 251]) * payload_size
        )
        for index in range(count)
    ]
    return make_email(subject="Attachment count flood", attachments=attachments)


def make_nested_report(depth: int) -> bytes:
    """Build a chain of attached emails for nested-depth enforcement tests."""
    current = make_email(subject="Nested leaf")
    for level in range(depth):
        current = make_report_envelope(
            [(f"nested-{level:02d}.eml", current)],
            subject=f"Nested envelope {level:02d}",
        )
    return current


def make_default_boundary_message(*, delta: int = 0) -> bytes:
    """Build a message with a 25 MiB + ``delta`` leaf when a full-size fixture is needed."""
    payload_size = 25 * 1024 * 1024 + delta
    return make_email(
        subject=f"Default attachment boundary {delta:+d}",
        attachments=[AttachmentFixture("boundary.bin", b"x" * payload_size)],
    )


def make_default_aggregate_message() -> bytes:
    """Build leaves whose decoded total is one byte over the 100 MiB default."""
    twenty_five_mib = 25 * 1024 * 1024
    attachments = [
        AttachmentFixture(f"aggregate-{index}.bin", b"x" * twenty_five_mib)
        for index in range(4)
    ]
    attachments.append(AttachmentFixture("aggregate-over.bin", b"x"))
    return make_email(subject="Default aggregate boundary", attachments=attachments)
