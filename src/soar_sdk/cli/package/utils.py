import requests


def phantom_get_login_session(
    base_url: str, username: str, password: str
) -> tuple[requests.Session, requests.Response]:
    """Log into phantom and get a token."""
    session = requests.Session()

    phantom_login_url = f"{base_url}/login"
    # get the cookies from the get method
    response = session.get(phantom_login_url, verify=False)
    body = {
        "username": username,
        "password": password,
        "csrfmiddlewaretoken": response.cookies.get_dict().get("csrftoken"),
    }
    login_response = session.post(
        phantom_login_url,
        data=body,
        verify=False,
        cookies=response.cookies,
        headers=dict(Referer=phantom_login_url),
    )
    print(login_response)

    return session, login_response


def phantom_post_with_csrf_token(
    base_url: str, endpoint: str, username: str, password: str, files: dict
) -> requests.Response:
    """Send a POST request with a CSRF token to the specified endpoint on the phantom instance."""
    headers = {}
    data = {}
    print("here")
    session, login_response = phantom_get_login_session(base_url, username, password)
    print("here2")

    csrftoken = login_response.cookies.get_dict().get("csrftoken")
    session_id = login_response.cookies["sessionid"]
    url = f"{base_url}/{endpoint}"
    headers["Referer"] = url
    headers["Cookie"] = f"csrftoken={csrftoken};sessionid={session_id}"
    data["csrfmiddlewaretoken"] = csrftoken

    return session.post(url, files=files, data=data, headers=headers, verify=False)
