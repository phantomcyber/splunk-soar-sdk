"""Tests for package utility functions."""

import pytest
import respx
import httpx

from soar_sdk.cli.package.utils import phantom_get_login_session, phantom_install_app


@pytest.mark.asyncio
@respx.mock
async def test_phantom_get_login_session_missing_csrf_token():
    """Test that phantom_get_login_session raises error when CSRF token is missing."""
    # Mock the home page without a csrftoken cookie
    respx.get("https://10.1.23.4/").respond(status_code=200)

    with pytest.raises(RuntimeError, match="Could not obtain CSRF token"):
        async with phantom_get_login_session("https://10.1.23.4", "admin", "password"):
            pass


@pytest.mark.asyncio
async def test_phantom_install_app_missing_csrf_token():
    """Test that phantom_install_app raises error when CSRF token is missing."""
    # Create a client without a csrftoken cookie
    async with httpx.AsyncClient(base_url="https://10.1.23.4") as client:
        with pytest.raises(RuntimeError, match="CSRF token not found in cookies"):
            await phantom_install_app(client, "/app_install", {"file": b"test_content"})
