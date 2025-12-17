import json

import pytest

from soar_sdk.asset_state import AssetState


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
