from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_MAX_WORKERS = 10


def parallel_map(
    func: Callable[[T], R],
    items: Sequence[T],
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[R]:
    """Apply func to each item concurrently, returning results in input order.

    Intended for independent blocking I/O calls (SOAR container and vault
    operations) that release the GIL while waiting on the network. Exceptions
    raised by func propagate to the caller once the corresponding result is
    read, preserving the semantics of a sequential map.
    """
    if not items:
        return []
    if len(items) == 1:
        return [func(items[0])]

    workers = min(max_workers, len(items))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(func, items))
