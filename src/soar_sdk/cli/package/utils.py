from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def phantom_get_login_session(
    base_url: str, username: str, password: str
) -> AsyncGenerator[httpx.AsyncClient]:
    """Contextmanager that creates an authenticated client with CSRF token handling."""
    # Set longer timeouts for large file uploads
    timeout = httpx.Timeout(30.0, read=60.0)
    async with httpx.AsyncClient(
        base_url=base_url,
        verify=False,  # noqa: S501
        timeout=timeout,
        auth=(username, password),  # Use HTTP Basic Auth
    ) as client:
        # Get CSRF token by hitting home page (follow redirects)
        response = await client.get("/", follow_redirects=True)
        response.raise_for_status()
        csrf_token = response.cookies.get("csrftoken")
        if not csrf_token:
            raise RuntimeError("Could not obtain CSRF token from SOAR instance")
        client.cookies.update(response.cookies)

        yield client


async def phantom_install_app(
    client: httpx.AsyncClient,
    endpoint: str,
    files: dict[str, bytes],
    force: bool = False,
) -> httpx.Response:
    """Send a POST request with a CSRF token to the specified endpoint using an authenticated token."""
    csrftoken = client.cookies.get("csrftoken")
    if not csrftoken:
        raise RuntimeError("CSRF token not found in cookies")

    response = await client.post(
        endpoint,
        files=files,
        data={"csrfmiddlewaretoken": csrftoken, "forced_installation": force},
        headers={
            "Referer": f"{client.base_url}/",
            "X-CSRFToken": csrftoken,
        },
    )

    return response
