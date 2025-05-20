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

    with pytest.raises(TypeError) as exception_info:

        @simple_app.on_poll()
        def second_on_poll(params: OnPollParams) -> Iterator[dict]:
            yield {"data": "another test"}

    assert "The 'on_poll' decorator can only be used once per App instance." in str(
        exception_info
    )


def test_on_poll_decoration_fails_when_not_generator(simple_app: App):
    """Test that the on_poll decorator requires a generator function."""
    with pytest.raises(TypeError) as exception_info:

        @simple_app.on_poll()
        def on_poll_function(params: OnPollParams):
            return {"data": "test"}  # Not yielding

    assert (
        "The on_poll function must be a generator (use 'yield') or return an Iterator."
        in str(exception_info)
    )


def test_on_poll_decoration_with_meta(simple_app: App):
    """Test that the on_poll decorator properly sets up metadata."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        """
        This polling function does nothing for now.
        """
        yield {"data": "test"}

    action = simple_app.actions_provider.get_action("on_poll")
    assert action is not None
    assert action.meta.action == "on poll"
    assert action == on_poll_function


def test_on_poll_function_called_with_params(simple_app: App):
    """Test that the on_poll function is called with parameters."""
    poll_fn = mock.Mock(return_value=iter([{"data": "test"}]))

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        poll_fn(params)
        yield {"data": "test"}

    client_mock = mock.Mock()

    params = OnPollParams(
        start_time=1000,
        end_time=2000,
        container_count=10,
        artifact_count=100,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)

    poll_fn.assert_called_once_with(params)
    assert result is True


def test_on_poll_works_with_iterator_functions(simple_app: App):
    """Test that the on_poll decorator works with functions that return iterators."""
    with mock.patch("inspect.isgeneratorfunction", return_value=True):

        @simple_app.on_poll()
        def on_poll_function(params: OnPollParams) -> Iterator[dict]:
            # Creating and returning an iterator instead of yielding
            return iter([{"data": "test artifact 1"}, {"data": "test artifact 2"}])

        client_mock = mock.Mock()

        params = OnPollParams(
            start_time=1000,
            end_time=2000,
            container_count=10,
            artifact_count=100,
            container_id=1,
        )

        result = on_poll_function(params, client=client_mock)

        assert result is True


def test_on_poll_empty_iterator(simple_app: App):
    """Test that the on_poll function works with empty iterators."""
    with mock.patch("inspect.isgeneratorfunction", return_value=True):

        @simple_app.on_poll()
        def on_poll_function(params: OnPollParams) -> Iterator[dict]:
            # Empty iterator - no artifacts to yield
            return iter([])

        client_mock = mock.Mock()

        params = OnPollParams(
            start_time=1000,
            end_time=2000,
            container_count=10,
            artifact_count=100,
            container_id=1,
        )

        result = on_poll_function(params, client=client_mock)

        assert result is True


def test_on_poll_return_none(simple_app: App):
    """Test that the on_poll function returns None should still work."""

    @simple_app.on_poll()
    def on_poll_function(params: OnPollParams) -> Iterator[dict]:
        if True:  # returning None
            return None
        yield {"data": "test"}

    client_mock = mock.Mock()

    params = OnPollParams(
        start_time=1000,
        end_time=2000,
        container_count=10,
        artifact_count=100,
        container_id=1,
    )

    result = on_poll_function(params, client=client_mock)

    assert result is True
