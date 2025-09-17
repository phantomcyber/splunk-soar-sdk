import httpx
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator


@asynccontextmanager
async def phantom_get_login_session(
    base_url: str, username: str, password: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Contextmanager that creates an authenticated client with CSRF token handling."""
    # Set longer timeouts for large file uploads
    timeout = httpx.Timeout(30.0, read=60.0)
    async with httpx.AsyncClient(
        base_url=base_url,
        verify=False,  # noqa: S501
        timeout=timeout,
    ) as client:
        # get the cookies from the get method
        response = await client.get("/login")
        response.raise_for_status()
        csrf_token = response.cookies.get("csrftoken")
        client.cookies.update(response.cookies)

        await client.post(
            "/login",
            data={
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": f"{base_url}/login"},
        )

        yield client


async def phantom_install_app(
    client: httpx.AsyncClient, endpoint: str, files: dict[str, bytes]
) -> httpx.Response:
    """Send a POST request with a CSRF token to the specified endpoint using an authenticated token."""
    csrftoken = client.cookies.get("csrftoken")

    response = await client.post(
        endpoint,
        files=files,
        data={"csrfmiddlewaretoken": csrftoken},
        headers={"Referer": f"{client.base_url}/{endpoint}"},
    )

    return response
