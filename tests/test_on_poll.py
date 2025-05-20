#!/usr/bin/python
from collections.abc import Iterator
import pytest
from unittest import mock

from soar_sdk.app import App
from soar_sdk.params import OnPollParams


def test_on_poll_decoration_fails_when_used_more_than_once(simple_app: App):
    """Test that the on_poll decorator can only be used once per app."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        yield {"data": "test"}

    with pytest.raises(TypeError, match=r"on_poll.+once per"):

        @simple_app.on_poll()
        def second_on_poll(params: OnPollParams) -> Iterator[dict]:
            yield {"data": "another test"}


def test_on_poll_decoration_fails_when_not_generator(simple_app: App):
    """Test that the on_poll decorator requires a generator function."""

    with pytest.raises(
        TypeError,
        match=r"The on_poll function must be a generator \(use 'yield'\) or return an Iterator.",
    ):

        @simple_app.on_poll()
        def on_poll_function(params: OnPollParams):
            return {"data": "test"}  # Not yielding


def test_on_poll_function_called_with_params(simple_app: App):
    """Test that the on_poll function is called with parameters."""
    poll_fn = mock.Mock(return_value=iter([{"data": "test"}]))

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        poll_fn(params)
        yield {"data": "test"}

    client_mock = mock.Mock()
    params = OnPollParams(
        start_time=0,
        end_time=1,
        container_count=10,
        artifact_count=100,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)

    poll_fn.assert_called_once_with(params)
    assert result is True


def test_on_poll_works_with_iterator_functions(simple_app: App):
    """Test that the on_poll decorator works with functions that return iterators."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        # Creating and returning an iterator
        return iter([{"data": "test artifact 1"}, {"data": "test artifact 2"}])

    client_mock = mock.Mock()
    params = OnPollParams(
        start_time=0,
        end_time=1,
        container_count=10,
        artifact_count=100,
    )

    result = on_poll_function(params, client=client_mock)

    assert result is True


def test_on_poll_empty_iterator(simple_app: App):
    """Test that the on_poll function works with empty iterators."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        # Empty iterator - no artifacts to yield
        return iter([])

    client_mock = mock.Mock()
    params = OnPollParams(
        start_time=0,
        end_time=1,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)

    assert result is True


def test_on_poll_raises_exception_propagates(simple_app: App):
    """Test that exceptions raised in the on_poll function are handled and return False."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        raise ValueError("poll error")
        yield  # pragma: no cover

    client_mock = mock.Mock()
    params = OnPollParams(
        start_time=0,
        end_time=1,
        container_count=10,
        artifact_count=100,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)
    assert result is False
    # Ensure the exception is logged
    client_mock.add_exception.assert_called()


def test_on_poll_multiple_yields(simple_app: App):
    """Test that multiple yielded items are processed by on_poll."""
    yielded = []

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        for i in range(3):
            yielded.append(i)
            yield {"data": i}

    client_mock = mock.Mock()
    params = OnPollParams(
        start_time=0,
        end_time=1,
        container_count=10,
        artifact_count=100,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)
    assert result is True
    assert yielded == [0, 1, 2]


def test_on_poll_decoration_with_meta(simple_app: App):
    """Test that the on_poll decorator properly sets up metadata."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        yield {"data": "test"}

    action = simple_app.actions_provider.get_action("on_poll")
    assert action is not None
    assert action.meta.action == "on poll"
    assert action == on_poll_function
