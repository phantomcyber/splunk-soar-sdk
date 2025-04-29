import httpx


async def phantom_get_login_session(
    base_url: str, username: str, password: str
) -> httpx.AsyncClient:
    """Log into phantom and return the authenticated client. The caller needs to close the client."""
    client = httpx.AsyncClient(base_url=base_url, verify=False)  # noqa: S501

    # get the cookies from the get method
    response = await client.get("/login")
    csrf_token = response.cookies.get("csrftoken")

    await client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": csrf_token,
        },
        cookies=response.cookies,
        headers={"Referer": f"{base_url}/login"},
    )

    return client


async def phantom_post(
    client: httpx.AsyncClient, endpoint: str, files: dict
) -> httpx.Response:
    """Send a POST request with a CSRF token to the specified endpoint using an authenticated token."""
    data = {}
    csrftoken = client.cookies.get("csrftoken")

    url = f"{client.base_url}/{endpoint}"
    headers = {"Referer": url}
    data = {"csrfmiddlewaretoken": csrftoken}

    response = await client.post(
        endpoint,
        files=files,
        data=data,
        headers=headers,
    )

    return response
