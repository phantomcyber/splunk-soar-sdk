"""Shared polling diagnostics preserve iteration and safely classify failures."""

import pytest

from soar_sdk.exceptions import PollingError
from soar_sdk.polling import diagnose_es_poll


@pytest.mark.parametrize("code", ["authentication", "mailbox"])
@pytest.mark.parametrize("status", [None, 100, 401, 599])
def test_safe_error(code, status):
    error = PollingError(code, status)
    assert error.polling_error_code == code
    assert error.status_code == status
    assert str(error)


def test_default_status():
    assert PollingError("mailbox").status_code is None


@pytest.mark.parametrize("code", ["secret", "", None, [], True])
def test_invalid_code(code):
    with pytest.raises(ValueError, match="Unsupported polling error code"):
        PollingError(code)


@pytest.mark.parametrize("status", [True, False, 99, 600, 401.0, "401"])
def test_invalid_status(status):
    with pytest.raises(ValueError, match="Polling HTTP status"):
        PollingError("authentication", status)


def test_conversion_after_yield_preserves_arguments_and_metadata():
    original = RuntimeError("private response token")
    seen = []

    def classify(error):
        seen.append(error)
        return "authentication", 401

    @diagnose_es_poll(classify)
    def poll(value, *, suffix):
        """Example handler."""
        yield value + suffix
        raise original

    assert poll.__name__ == "poll"
    assert poll.__doc__ == "Example handler."
    generator = poll("first", suffix=" finding")
    assert next(generator) == "first finding"
    with pytest.raises(PollingError) as caught:
        next(generator)
    assert seen == [original]
    assert caught.value.polling_error_code == "authentication"
    assert caught.value.status_code == 401
    assert "private" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


@pytest.mark.parametrize(
    "result", [None, ("unknown", None), ("mailbox", 999), (), ("mailbox",)]
)
def test_unknown_or_invalid_classification_preserves_original(result):
    original = ConnectionError("private response")

    @diagnose_es_poll(lambda error: result)
    def poll():
        raise original
        yield

    with pytest.raises(ConnectionError) as caught:
        list(poll())
    assert caught.value is original


def test_classifier_failure_preserves_original():
    original = RuntimeError("original")

    def classify(error):
        raise ValueError("classifier failure")

    @diagnose_es_poll(classify)
    def poll():
        raise original
        yield

    with pytest.raises(RuntimeError) as caught:
        list(poll())
    assert caught.value is original


def test_explicit_error_is_not_reclassified():
    original = PollingError("mailbox")

    def classify(error):
        pytest.fail("Existing diagnostics must pass through")

    @diagnose_es_poll(classify)
    def poll():
        raise original
        yield

    with pytest.raises(PollingError) as caught:
        list(poll())
    assert caught.value is original


@pytest.mark.parametrize("close_early", [False, True])
def test_success_and_generator_cleanup(close_early):
    closed = []

    def classify(error):
        pytest.fail("Successful polling must not be classified")

    @diagnose_es_poll(classify)
    def poll():
        try:
            yield 1
            yield 2
        finally:
            closed.append(True)

    generator = poll()
    assert next(generator) == 1
    if close_early:
        generator.close()
    else:
        assert list(generator) == [2]
    assert closed == [True]


def test_failure_before_iterator_creation():
    @diagnose_es_poll(lambda error: ("mailbox", 404))
    def poll():
        raise RuntimeError("private response")

    with pytest.raises(PollingError) as caught:
        list(poll())
    assert caught.value.status_code == 404
