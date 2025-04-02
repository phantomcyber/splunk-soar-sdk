import typing
from typing import Any, Protocol

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params


class Action(Protocol):
    meta: ActionMeta
    params_class: type[Params]

    def __call__(self, *args, **kwargs) -> bool: ...  # type: ignore


def action_protocol(func: Any) -> Action:
    return typing.cast(Action, func)
