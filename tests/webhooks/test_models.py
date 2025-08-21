import base64
from io import BytesIO, StringIO
import pytest


from soar_sdk.webhooks.models import WebhookResponse


def test_set_header():
    response = WebhookResponse(
        status_code=200,
        headers=[("Content-Type", "text/plain")],
        content="Hello, World!",
    )

    # Set a new header
    response.set_header("X-Custom-Header", "CustomValue")
    assert ("X-Custom-Header", "CustomValue") in response.headers

    # Update an existing header
    response.set_header("Content-Type", "application/json")
    assert ("Content-Type", "application/json") in response.headers


def test_clear_header():
    response = WebhookResponse(
        status_code=200,
        headers=[("Content-Type", "text/plain"), ("X-Custom-Header", "CustomValue")],
        content="Hello, World!",
    )

    # Clear an existing header
    response.clear_header("Content-Type")
    assert ("Content-Type", "text/plain") not in response.headers

    # Attempt to clear a non-existing header
    with pytest.raises(IndexError):
        response.clear_header("Non-Existing-Header")


def test_text_response():
    content = "Hello, World!"
    status_code = 200
    extra_headers = {"X-Custom-Header": "CustomValue"}

    response = WebhookResponse.text_response(content, status_code, extra_headers)

    assert response.content == content
    assert response.status_code == status_code
    assert ("Content-Type", "text/plain") in response.headers
    assert ("X-Custom-Header", "CustomValue") in response.headers


def test_file_response():
    content = "Hello, World!"
    fd = StringIO(content)
    status_code = 200
    extra_headers = {"X-Custom-Header": "CustomValue"}
    filename = "test.txt"
    content_type = "text/plain"

    response = WebhookResponse.file_response(
        fd, filename, content_type, status_code, extra_headers
    )

    assert response.content == content
    assert response.status_code == status_code
    assert ("Content-Type", content_type) in response.headers
    assert ("X-Custom-Header", "CustomValue") in response.headers
    assert (
        "Content-Disposition",
        f'attachment; filename="{filename}"',
    ) in response.headers


def test_binary_file_response():
    content = b"\x89PNG\r\n\x1a\n"
    fd = BytesIO(content)
    content_base64 = base64.b64encode(content).decode()
    fd.seek(0)
    status_code = 200
    filename = "test.png"
    content_type = "image/png"

    response = WebhookResponse.file_response(fd, filename, content_type, status_code)

    assert response.content == content_base64
    assert response.status_code == status_code
    assert ("Content-Type", content_type) in response.headers
    assert (
        "Content-Disposition",
        f'attachment; filename="{filename}"',
    ) in response.headers
    assert response.is_base64_encoded


def test_file_response_guess_content_type():
    content = "Hello, World!"
    fd = StringIO(content)
    status_code = 200
    extra_headers = {"X-Custom-Header": "CustomValue"}
    filename = "test.txt"

    response = WebhookResponse.file_response(
        fd, filename, None, status_code, extra_headers
    )

    assert response.content == content
    assert response.status_code == status_code
    assert ("Content-Type", "text/plain") in response.headers
    assert ("X-Custom-Header", "CustomValue") in response.headers
    assert (
        "Content-Disposition",
        f'attachment; filename="{filename}"',
    ) in response.headers


def test_file_response_cannot_guess_content_type():
    content = "Hello, World!"
    fd = StringIO(content)
    status_code = 200
    filename = "test.unknown"

    with pytest.raises(ValueError, match="Could not determine content type"):
        WebhookResponse.file_response(fd, filename, None, status_code)
