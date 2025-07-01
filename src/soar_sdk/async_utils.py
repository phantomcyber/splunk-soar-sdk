import asyncio
import inspect
from typing import Any
from collections.abc import AsyncGenerator


def is_coroutine(obj: Any) -> bool:  # noqa: ANN401
    return inspect.iscoroutine(obj)


def is_async_generator(obj: Any) -> bool:  # noqa: ANN401
    return inspect.isasyncgen(obj)


async def async_generator_to_list(agen: AsyncGenerator[Any, None]) -> list[Any]:
    result = []
    async for item in agen:
        result.append(item)
    return result


def run_async_if_needed(result: Any) -> Any:  # noqa: ANN401
    if is_coroutine(result):
        return asyncio.run(result)
    elif is_async_generator(result):
        # Convert async generator to list
        return asyncio.run(async_generator_to_list(result))
    return result
