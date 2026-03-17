import typing
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from soar_sdk.meta.actions import ActionMeta
    from soar_sdk.params import Params


@runtime_checkable
class NamedCallable(Protocol):
    """Protocol for callables that have __name__, __module__, and __globals__ attributes (i.e. real functions)."""

    __name__: str
    __module__: str
    __globals__: dict[str, Any]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        """Call the function."""
        ...


class Action(Protocol):
    """Type interface for an action definition."""

    meta: "ActionMeta"
    params_class: "type[Params] | None" = None

    def __call__(self, *args: Any, **kwargs: Any) -> bool:  # noqa: ANN401
        """Execute the action function."""
        ...


def action_protocol(func: Callable) -> Action:
    """Convert a generic callable into an Action protocol, purely for typing purposes."""
    return typing.cast(Action, func)
