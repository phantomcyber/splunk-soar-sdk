import typing
from typing import Any, Callable, Optional, Protocol

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params


class Action(Protocol):
    """Type interface for an action definition."""

    meta: ActionMeta
    params_class: Optional[type[Params]] = None

    def __call__(self, *args: Any, **kwargs: Any) -> bool:  # noqa: ANN401
        """Execute the action function."""
        ...


def action_protocol(func: Callable) -> Action:
    """Convert a generic callable into an Action protocol, purely for typing purposes."""
    return typing.cast(Action, func)
