import asyncio
import inspect
from typing import Any, TypeVar, overload
from collections.abc import AsyncGenerator, Coroutine


T = TypeVar("T")


def is_coroutine(obj: Any) -> bool:  # noqa: ANN401
    return inspect.iscoroutine(obj)


def is_async_generator(obj: Any) -> bool:  # noqa: ANN401
    return inspect.isasyncgen(obj)


async def async_generator_to_list(agen: AsyncGenerator[T, None]) -> list[T]:
    result: list[T] = []
    # Python 3.9 coverage limitation with async for loops
    async for item in agen:  # pragma: no cover
        result.append(item)
    return result


@overload
def run_async_if_needed(result: Coroutine[Any, Any, T]) -> T: ...


@overload
def run_async_if_needed(result: AsyncGenerator[T, None]) -> list[T]: ...


@overload
def run_async_if_needed(result: T) -> T: ...


def run_async_if_needed(result: Any) -> Any:
    if is_coroutine(result):
        return asyncio.run(result)
    elif is_async_generator(result):
        # Convert async generator to list
        return asyncio.run(async_generator_to_list(result))
    return result
