import pytest
from pydantic import ValidationError

from soar_sdk.models.attachment_input import AttachmentInput


def test_attachment_input_with_file_content():
    """Test AttachmentInput with file_content."""
    attachment = AttachmentInput(
        file_content="test content",
        file_name="test.txt",
    )
    assert attachment.file_content == "test content"
    assert attachment.file_location is None


def test_attachment_input_with_file_location():
    """Test AttachmentInput with file_location."""
    attachment = AttachmentInput(
        file_location="/tmp/test.txt",
        file_name="test.txt",
    )
    assert attachment.file_location == "/tmp/test.txt"
    assert attachment.file_content is None


def test_attachment_input_with_metadata():
    """Test AttachmentInput with metadata."""
    attachment = AttachmentInput(
        file_content="test",
        file_name="test.txt",
        metadata={"key": "value"},
    )
    assert attachment.metadata == {"key": "value"}


def test_attachment_input_missing_both_sources():
    """Test AttachmentInput fails with neither file_content file_location provided."""
    with pytest.raises(
        ValidationError, match="Must provide either file_content or file_location"
    ):
        AttachmentInput(file_name="test.txt", file_content=None, file_location=None)


def test_attachment_input_both_sources_provided():
    """Test AttachmentInput fails with both file_content file_location provided."""
    with pytest.raises(
        ValidationError, match="Cannot provide both file_content and file_location"
    ):
        AttachmentInput(
            file_content="test",
            file_location="/tmp/test.txt",
            file_name="test.txt",
        )
