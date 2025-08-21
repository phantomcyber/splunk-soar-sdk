import asyncio

from soar_sdk.params import Params, Param
from soar_sdk.action_results import ActionOutput
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact


class _TestParams(Params):
    test_value: str = Param(description="Test Value")


class _TestOutput(ActionOutput):
    result: str


def test_action_decorator_async_support(app_with_action):
    """Test that @action decorator supports async functions."""

    @app_with_action.action(params_class=_TestParams, identifier="async_action")
    async def async_action(params: _TestParams) -> _TestOutput:
        await asyncio.sleep(0.01)  # Async operation
        return _TestOutput(result=f"async_{params.test_value}")

    actions = app_with_action.get_actions()
    assert "async_action" in actions


def test_webhook_decorator_async_support(simple_app):
    """Test that @webhook decorator supports async functions."""
    simple_app.enable_webhooks()

    @simple_app.webhook("/async")
    async def async_webhook(request: WebhookRequest) -> WebhookResponse:
        await asyncio.sleep(0.01)  # Async operation
        return WebhookResponse(status_code=200, content="async response")

    router = simple_app.webhook_router
    assert router is not None


def test_async_generator_support():
    """Test that async generators work with the on_poll decorator."""
    from soar_sdk.async_utils import run_async_if_needed

    async def async_gen():
        await asyncio.sleep(0.01)  # Async operation
        yield Container(name="test_container")
        yield Artifact(name="test_artifact", cef={})

    result = run_async_if_needed(async_gen())
    assert len(result) == 2
    assert isinstance(result[0], Container)
    assert isinstance(result[1], Artifact)


def test_view_handler_async_support(simple_app):
    """Test that @view_handler decorator supports async functions."""

    @simple_app.view_handler()
    async def async_view_handler(outputs) -> str:
        await asyncio.sleep(0.01)  # Async operation
        return "<html>example view</html>"

    assert callable(async_view_handler)
