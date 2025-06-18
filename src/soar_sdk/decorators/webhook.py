import inspect
from functools import wraps
from typing import Optional

from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse, WebhookHandler


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soar_sdk.app import App


class WebhookDecorator:
    """
    Class-based decorator for webhook functionality.
    """

    def __init__(
        self, app: "App", url_pattern: str, allowed_methods: Optional[list[str]] = None
    ) -> None:
        self.app = app
        self.url_pattern = url_pattern
        self.allowed_methods = allowed_methods

    def __call__(self, function: WebhookHandler) -> WebhookHandler:
        """
        Decorator for the webhook handler function. Adds the specific meta
        information to the action passed to the generator. Validates types used on
        the action arguments and adapts output for fast and seamless development.
        """
        if self.app.webhook_router is None:
            raise RuntimeError("Webhooks are not enabled for this app.")

        @wraps(function)
        def webhook_wrapper(
            request: WebhookRequest,
        ) -> WebhookResponse:
            # Inject soar_client if the function expects it
            kwargs = {}
            sig = inspect.signature(function)
            if "soar" in sig.parameters:
                kwargs["soar"] = self.app.soar_client
            return function(request, **kwargs)

        self.app.webhook_router.add_route(
            self.url_pattern,
            webhook_wrapper,
            methods=self.allowed_methods,
        )

        return webhook_wrapper
