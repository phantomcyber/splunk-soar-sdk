from typing import Any, Protocol

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params


class MetaDescribed(Protocol):
    meta: ActionMeta
    params_klass: type[Params]

    def __call__(self, *args, **kwargs) -> bool: ...


def meta_described(func: Any) -> MetaDescribed:
    return func
