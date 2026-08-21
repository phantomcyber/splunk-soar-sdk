import json

import pytest
import pytest_mock

import soar_sdk.asset_state
from soar_sdk.asset_state import AssetState
from soar_sdk.shims.phantom.encryption_helper import encryption_helper


@pytest.fixture
def noop_encryption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate an install whose encryption helper returns values unchanged.

    RPC automation brokers behave this way, since SOAR encrypts the asset state
    on their behalf.
    """
    monkeypatch.setattr(
        encryption_helper, "encrypt", lambda plain, salt="unused-salt": plain
    )
    monkeypatch.setattr(
        encryption_helper, "decrypt", lambda cipher, salt="unused-salt": cipher
    )


def test_asset_state_full_accessors(example_state: AssetState):
    assert example_state.get_all() == {}

    initial = {
        "string_val": "hello world",
        "int_val": 42,
        "float_val": 13.37,
        "bool_val": True,
        "none_val": None,
    }
    example_state.put_all(initial)
    assert example_state.get_all() == initial

    updated = {"string_val": "hello again"}
    example_state.put_all(updated)
    assert example_state.get_all() == updated

    example_state.clear()
    assert example_state.get_all() == {}


def test_asset_state_key_accessors(example_state: AssetState):
    example_state.put_all(
        {
            "string_val": "hello world",
            "int_val": 42,
            "float_val": 13.37,
            "bool_val": True,
            "none_val": None,
        }
    )

    assert example_state.get("int_val") == 42
    assert example_state["bool_val"]

    example_state.update({"float_val": 3.14})
    example_state["bool_val"] = False

    example_state.pop("none_val")
    del example_state["string_val"]

    assert example_state.get_all() == {
        "int_val": 42,
        "float_val": 3.14,
        "bool_val": False,
    }


def test_magic_methods(example_state: AssetState):
    example_state.put_all({"foo": 0, "bar": "baz", "bap": True})

    assert set(example_state) == {"foo", "bar", "bap"}
    assert len(example_state) == 3


def test_state_is_encrypted(example_state: AssetState):
    example_state.put_all({"unreadable": True})

    raw_state = example_state.backend.load_state().get(example_state.state_key)
    with pytest.raises(json.JSONDecodeError):
        # If the state string is encrypted, then it won't be JSON-decodable.
        json.loads(raw_state)


def test_state_can_be_stored_as_plaintext(example_provider):
    plaintext_state = AssetState(example_provider, "example", "1", encrypted=False)

    plaintext_state.put_all({"key": "original"})
    plaintext_state["item"] = "value"

    assert plaintext_state.backend.load_state()["example"] == {
        "key": "original",
        "item": "value",
    }
    assert plaintext_state.get_all() == {"key": "original", "item": "value"}

    plaintext_state.begin_transaction()
    plaintext_state["key"] = "updated"

    assert plaintext_state.backend.load_state()["example"] == {
        "key": "original",
        "item": "value",
    }

    plaintext_state.commit()

    assert plaintext_state.backend.load_state()["example"] == {
        "key": "updated",
        "item": "value",
    }


def test_plaintext_state_reads_legacy_encrypted_state(example_provider):
    encrypted_state = AssetState(example_provider, "example", "1")
    encrypted_state.put_all({"legacy": True})

    plaintext_state = AssetState(example_provider, "example", "1", encrypted=False)

    assert plaintext_state.get_all() == {"legacy": True}

    plaintext_state["new"] = "value"

    assert plaintext_state.backend.load_state()["example"] == {
        "legacy": True,
        "new": "value",
    }


def test_encrypted_state_reads_legacy_plaintext_state(example_provider):
    plaintext_state = AssetState(example_provider, "example", "1", encrypted=False)
    plaintext_state.put_all({"legacy": True})

    encrypted_state = AssetState(example_provider, "example", "1")

    assert encrypted_state.get_all() == {"legacy": True}

    encrypted_state["new"] = "value"

    raw_state = encrypted_state.backend.load_state()["example"]
    assert isinstance(raw_state, str)
    assert json.loads(encryption_helper.decrypt(raw_state, "1")) == {
        "legacy": True,
        "new": "value",
    }


def test_noop_encryption_stores_readable_state(
    example_state: AssetState, noop_encryption: None
):
    example_state.put_all({"token": "abc"})
    example_state["expires_in"] = 3600

    # A no-op helper cannot produce ciphertext, so the state is stored as a
    # mapping rather than a string which only looks encrypted.
    assert example_state.backend.load_state()["example"] == {
        "token": "abc",
        "expires_in": 3600,
    }
    assert example_state.get_all() == {"token": "abc", "expires_in": 3600}


def test_noop_encryption_reads_legacy_encrypted_state(
    example_state: AssetState, noop_encryption: None
):
    example_state.backend.save_state({"example": json.dumps({"legacy": True})})

    assert example_state.get_all() == {"legacy": True}


def test_state_is_stored_as_plaintext_when_encryption_fails(
    example_state: AssetState, monkeypatch: pytest.MonkeyPatch
):
    def fail_encrypt(plain, salt="unused-salt"):
        raise ValueError("no encryption key available")

    monkeypatch.setattr(encryption_helper, "encrypt", fail_encrypt)
    example_state.put_all({"key": "value"})

    assert example_state.backend.load_state()["example"] == {"key": "value"}
    assert example_state.get_all() == {"key": "value"}


def test_state_is_stored_as_plaintext_when_encryption_returns_nothing(
    example_state: AssetState, monkeypatch: pytest.MonkeyPatch
):
    # On-prem encryption stores return an empty string rather than raising.
    monkeypatch.setattr(
        encryption_helper, "encrypt", lambda plain, salt="unused-salt": ""
    )
    example_state.put_all({"key": "value"})

    assert example_state.backend.load_state()["example"] == {"key": "value"}
    assert example_state.get_all() == {"key": "value"}


def test_get_all_reads_plaintext_when_decryption_fails(example_state: AssetState):
    example_state.backend.save_state({"example": json.dumps({"key": "value"})})

    # The stub helper cannot decrypt a value it did not encrypt.
    assert example_state.get_all() == {"key": "value"}


def test_get_all_reads_plaintext_when_decryption_returns_nothing(
    example_state: AssetState, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        encryption_helper, "decrypt", lambda cipher, salt="unused-salt": ""
    )
    example_state.backend.save_state({"example": json.dumps({"key": "value"})})

    assert example_state.get_all() == {"key": "value"}


@pytest.mark.parametrize("stored_state", ["ZW5jcnlwdGVkLWVsc2V3aGVyZQ==", "1337"])
def test_unreadable_state_is_discarded(
    example_state: AssetState,
    noop_encryption: None,
    mocker: pytest_mock.MockerFixture,
    stored_state: str,
):
    error = mocker.patch.object(soar_sdk.asset_state.logger, "error")
    example_state.backend.save_state({"example": stored_state})

    assert example_state.get_all() == {}
    error.assert_called_once()


def test_transaction_commit_persists(example_state: AssetState):
    example_state.put_all({"key": "original"})

    example_state.begin_transaction()
    example_state["key"] = "updated"
    example_state["new_key"] = "new_value"

    # Backend still has the original value during transaction
    raw_state = example_state.backend.load_state() or {}

    decrypted = json.loads(
        encryption_helper.decrypt(
            raw_state[example_state.state_key], example_state.asset_id
        )
    )
    assert decrypted == {"key": "original"}

    example_state.commit()

    assert example_state.get_all() == {"key": "updated", "new_key": "new_value"}


def test_transaction_commit_failure_preserves_buffer_for_rollback(
    example_state: AssetState, monkeypatch: pytest.MonkeyPatch
):
    example_state.put_all({"key": "original"})
    example_state.begin_transaction()
    example_state["key"] = "updated"

    def fail_save(_state):
        raise OSError("disk full")

    monkeypatch.setattr(example_state.backend, "save_state", fail_save)

    with pytest.raises(OSError, match="disk full"):
        example_state.commit()

    assert example_state.in_transaction
    assert example_state.get_all() == {"key": "updated"}
    example_state.rollback()


def test_transaction_rollback_discards(example_state: AssetState):
    example_state.put_all({"key": "original"})

    example_state.begin_transaction()
    example_state["key"] = "should_be_discarded"
    example_state["extra"] = "also_discarded"
    example_state.rollback()

    assert example_state.get_all() == {"key": "original"}


def test_transaction_reads_see_buffered_writes(example_state: AssetState):
    example_state.put_all({"a": 1})

    example_state.begin_transaction()
    example_state["b"] = 2
    assert example_state["b"] == 2
    assert example_state.get_all() == {"a": 1, "b": 2}
    example_state.rollback()


def test_transaction_double_begin_raises(example_state: AssetState):
    example_state.begin_transaction()
    with pytest.raises(RuntimeError, match="already active"):
        example_state.begin_transaction()
    example_state.rollback()


def test_commit_without_transaction_raises(example_state: AssetState):
    with pytest.raises(RuntimeError, match="No active transaction"):
        example_state.commit()


def test_rollback_without_transaction_raises(example_state: AssetState):
    with pytest.raises(RuntimeError, match="No active transaction"):
        example_state.rollback()


def test_writes_outside_transaction_persist_immediately(example_state: AssetState):
    example_state["key"] = "persisted"
    assert example_state.get_all() == {"key": "persisted"}
    assert not example_state.in_transaction


def test_get_all_with_force_reload(example_state: AssetState):
    example_state.put_all({"key": "original_value"})

    reload_called = False
    original_reload = example_state.backend.reload_state_from_file

    def mock_reload(asset_id):
        nonlocal reload_called
        reload_called = True
        return original_reload(asset_id) if callable(original_reload) else {}

    example_state.backend.reload_state_from_file = mock_reload

    result = example_state.get_all(force_reload=True)

    assert reload_called is True
    assert result == {"key": "original_value"}
