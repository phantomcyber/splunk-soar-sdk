from soar_sdk.app_client import AppClient
from soar_sdk.abstract import SOARClientAuth


def test_update_client(
    simple_connector: AppClient,
    soar_client_auth: SOARClientAuth,
    mock_get_any_soar_call,
    mock_post_any_soar_call,
):
    simple_connector.update_client(soar_client_auth, 1)
    assert mock_get_any_soar_call.call_count == 1
    request = mock_get_any_soar_call.calls[0].request
    assert request.url == "https://10.34.5.6/login"
    assert simple_connector.client.headers["X-CSRFToken"] == "mocked_csrf_token"

    assert mock_post_any_soar_call.call_count == 1
    post_request = mock_post_any_soar_call.calls[0].request
    assert post_request.url == "https://10.34.5.6/login"

    assert (
        simple_connector.client.headers["Cookie"]
        == "sessionid=mocked_session_id;csrftoken=mocked_csrf_token"
    )


def test_authenticate_soar_client_on_platform(
    simple_connector: AppClient,
    soar_client_auth_token: SOARClientAuth,
    mock_get_any_soar_call,
):
    simple_connector.authenticate_soar_client(soar_client_auth_token)
    assert mock_get_any_soar_call.call_count == 1
