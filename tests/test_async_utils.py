import asyncio
import contextlib
from unittest.mock import Mock

from soar_sdk.async_utils import is_coroutine, run_async_if_needed, is_async_generator


def test_is_async_generator():
    """Test that is_async_generator correctly identifies async generators. (on_poll)"""

    async def async_gen():
        yield "item1"
        yield "item2"

    gen = async_gen()
    assert is_async_generator(gen) is True
    with contextlib.suppress(Exception):
        asyncio.run(gen.aclose())

    assert is_async_generator("string") is False
    assert is_async_generator(10) is False
    assert is_async_generator([1, 2, 3]) is False


def test_is_coroutine_detection():
    """Test that is_coroutine correctly identifies coroutines"""

    async def async_func():
        return "async result"

    coro = async_func()
    assert is_coroutine(coro) is True
    coro.close()

    assert is_coroutine("string") is False
    assert is_coroutine(10) is False
    assert is_coroutine(None) is False


def test_run_async_if_needed_with_coroutines():
    """Test that run_async_if_needed properly executes coroutines."""

    async def simple_async():
        return "async result"

    async def async_with_await():
        await asyncio.sleep(0.01)  # Async operation
        return "delayed result"

    result = run_async_if_needed(simple_async())
    assert result == "async result"

    result = run_async_if_needed(async_with_await())
    assert result == "delayed result"


def test_run_async_if_needed_with_regular_values():
    """Test that run_async_if_needed passes through non-coroutines unchanged."""
    assert run_async_if_needed("string") == "string"
    assert run_async_if_needed(10) == 10
    assert run_async_if_needed(None) is None

    mock_obj = Mock()
    assert run_async_if_needed(mock_obj) is mock_obj


def test_run_async_if_needed_with_async_generators():
    """Test that run_async_if_needed properly handles async generators."""

    async def async_gen():
        yield "item1"
        await asyncio.sleep(0.01)  # Async operation
        yield "item2"

    result = run_async_if_needed(async_gen())
    assert result == ["item1", "item2"]
