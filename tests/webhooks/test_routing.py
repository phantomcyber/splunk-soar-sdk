import pytest

from soar_sdk.asset import BaseAsset
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse
from soar_sdk.webhooks.routing import Router, RouteConflictError


def test_route_invalid_method() -> None:
    """
    Test that adding a route with an invalid method raises an error.
    """
    router = Router()

    with pytest.raises(ValueError, match="Invalid HTTP method: INVALID"):
        router.add_route(
            "/test/<param>",
            lambda x: None,
            methods=["GET", "INVALID"],
        )


@pytest.mark.parametrize(
    "route,should_raise",
    (
        ("/models/<model_id>/permissions", False),  # Different constant segment
        ("/models/<model_id>/properties", True),  # Exact match
        ("/models/<model_id>/properties/", True),  # Trailing slash
        (
            "/models/<other_model_id>/properties",
            True,
        ),  # Conflict with different parameter name
        ("/models/default/properties", False),  # constant instead of param
        ("/models/<model_id>/properties/<property_name>", False),  # Sub-route
        (
            "/models/<model_id>/properties/<property_name>/<sub_property>",
            False,
        ),  # Deeper sub-route
        (
            "/models/<model_id>/properties/<property_name>/<sub_property>/<extra>",
            False,
        ),  # Extra segment
    ),
)
def test_route_conflicts(route: str, should_raise: bool) -> None:
    """
    Test that route conflicts are detected correctly.
    """
    base_route = "/models/<model_id>/properties"

    router = Router()
    router.add_route(base_route, lambda x: None)

    if should_raise:
        with pytest.raises(RouteConflictError):
            router.add_route(route, lambda x: None)
    else:
        router.add_route(route, lambda x: None)


def test_handle_route() -> None:
    """
    Test that routes are handled correctly.
    """
    router = Router()

    def test_handler(request: WebhookRequest, param: str) -> WebhookResponse:
        assert request.soar_auth_token == "test_token"
        assert request.soar_base_url == "https://localhost:9999"
        assert request.asset_id == 1
        return WebhookResponse.text_response(
            content=f"Handled {param}",
            status_code=200,
        )

    router.add_route("/test/<param>", test_handler)

    response = router.handle_request(
        WebhookRequest(
            method="GET",
            headers={},
            path_parts=["test", "123"],
            query={},
            body=None,
            asset=BaseAsset(),
            asset_id=1,
            soar_auth_token="test_token",
            soar_base_url="https://localhost:9999",
        )
    )
    assert response.status_code == 200
    assert response.headers == [("Content-Type", "text/plain")]
    assert response.content == "Handled 123"


def test_handle_route_404() -> None:
    """
    Test that 404 is returned for unmatched routes.
    """
    router = Router()

    def test_handler(request: WebhookRequest, param: str) -> WebhookResponse:
        return WebhookResponse.text_response(
            content=f"Handled {param}",
            status_code=200,
        )

    router.add_route("/test/<param>", test_handler)

    response = router.handle_request(
        WebhookRequest(
            method="GET",
            headers={},
            path_parts=["nonexistent", "123"],
            query={},
            body=None,
            asset=BaseAsset(),
            asset_id=1,
            soar_auth_token="test_token",
            soar_base_url="https://localhost:9999",
        )
    )
    assert response.status_code == 404


def test_handle_route_405() -> None:
    """
    Test that 405 is returned for unsupported methods.
    """
    router = Router()

    def test_handler(request: WebhookRequest, param: str) -> WebhookResponse:
        return WebhookResponse.text_response(
            content=f"Handled {param}",
            status_code=200,
        )

    router.add_route("/test/<param>", test_handler, methods=["GET"])

    response = router.handle_request(
        WebhookRequest(
            method="POST",
            headers={},
            path_parts=["test", "123"],
            query={},
            body=None,
            asset=BaseAsset(),
            asset_id=1,
            soar_auth_token="test_token",
            soar_base_url="https://localhost:9999",
        )
    )
    assert response.status_code == 405
