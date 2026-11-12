"""Execution-local summary and message storage for SDK actions."""

__lazy_modules__ = {
    "collections.abc",
    "functools",
    "typing",
    "contextlib",
    "contextvars",
    "dataclasses",
    "soar_sdk.action_results",
}

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any

from soar_sdk.action_results import ActionOutput


@dataclass
class ActionContext:
    """Mutable state shared with an action's asynchronous execution context."""

    client: object
    summary: ActionOutput | None = None
    message: str = ""


_current: ContextVar[ActionContext | None] = ContextVar("action_context", default=None)


def get_action_context(client: object) -> ActionContext | None:
    """Return context only for the client executing the current action."""
    context = _current.get()
    return context if context is not None and context.client is client else None


@contextmanager
def action_context(client: object) -> Iterator[None]:
    """Isolate action state, restoring any enclosing execution on exit."""
    token = _current.set(ActionContext(client))
    try:
        yield
    finally:
        _current.reset(token)


def isolate_action_context(
    default_client: object,
) -> Callable[[Callable[..., bool]], Callable[..., bool]]:
    """Wrap an action with a fresh context for its effective SOAR client."""

    def decorate(function: Callable[..., bool]) -> Callable[..., bool]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> bool:  # noqa: ANN401
            client = kwargs.get("soar", args[1] if len(args) > 1 else default_client)
            with action_context(client):
                return function(*args, **kwargs)

        return wrapped

    return decorate
