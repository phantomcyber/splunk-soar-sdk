"""Shared diagnostics for connector-owned ES polling generators."""

__lazy_modules__ = {
    "collections.abc",
    "contextlib",
    "functools",
    "typing",
    "soar_sdk.exceptions",
}

from collections.abc import Callable, Generator, Iterator
from contextlib import suppress
from functools import wraps
from typing import Protocol

from soar_sdk.exceptions import PollingError


class _PollDiagnosticsDecorator(Protocol):
    def __call__[**P, T](
        self, handler: Callable[P, Iterator[T]], /
    ) -> Callable[P, Generator[T]]: ...


def diagnose_es_poll(
    classify_error: Callable[[Exception], tuple[str, int | None] | None],
) -> _PollDiagnosticsDecorator:
    """Translate known connector errors into safe polling diagnostics.

    Args:
        classify_error: Connector-specific classifier returning an allowlisted
            reason and optional HTTP status, or ``None`` for unknown failures.
            If classification fails or returns invalid diagnostics, the original
            exception is re-raised. SDK polling errors pass through unchanged.

    Returns:
        A decorator that preserves yielded items and generator cleanup. It does
        not retry polling or change checkpoints. Place it below ``@app.on_es_poll()``.
    """

    def decorate[**P, T](
        handler: Callable[P, Iterator[T]], /
    ) -> Callable[P, Generator[T]]:
        @wraps(handler)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> Generator[T]:
            try:
                yield from handler(*args, **kwargs)
            except PollingError:
                raise
            except Exception as error:
                diagnostic = None
                with suppress(Exception):
                    reason = classify_error(error)
                    if reason is not None:
                        code, status = reason
                        diagnostic = PollingError(code, status)
                if diagnostic is not None:
                    raise diagnostic from None
                raise

        return wrapped

    return decorate
