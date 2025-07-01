import inspect
from functools import wraps
from typing import Optional
from pathlib import Path

from soar_sdk.cli.path_utils import relative_to_cwd
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse, WebhookHandler
from soar_sdk.meta.webhooks import WebhookRouteMeta
from soar_sdk.async_utils import run_async_if_needed


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
        if self.app.webhook_router is None or self.app.webhook_meta is None:
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
            result = function(request, **kwargs)
            return run_async_if_needed(result)

        stack = inspect.stack()
        declaration_path_absolute = stack[1].filename
        declaration_path = relative_to_cwd(Path(declaration_path_absolute))
        _, declaration_lineno = inspect.getsourcelines(function)

        self.app.webhook_router.add_route(
            self.url_pattern,
            webhook_wrapper,
            methods=self.allowed_methods,
        )

        self.app.webhook_meta.routes.append(
            WebhookRouteMeta(
                url_pattern=self.url_pattern,
                allowed_methods=self.allowed_methods or ["GET", "POST"],
                declaration_path=declaration_path,
                declaration_lineno=declaration_lineno,
            )
        )

        return webhook_wrapper
