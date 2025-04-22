import typing
from typing import Any, Callable, Protocol

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params


class Action(Protocol):
    meta: ActionMeta
    params_class: type[Params]

    def __call__(self, *args: Any, **kwargs: Any) -> bool: ...  # noqa: ANN401


def action_protocol(func: Callable) -> Action:
    return typing.cast(Action, func)
