from unittest import mock

import pytest

from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.crypto import encrypt
from soar_sdk.exceptions import AssetMisconfiguration
from soar_sdk.input_spec import AppConfig, InputSpecification
from soar_sdk.shims.phantom_common.credential_managers import (
    apply_credential_management,
)

CM_MODULE = "soar_sdk.shims.phantom_common.credential_managers"


def test_no_credential_management_returns_empty():
    config = {"api_key": "direct_value"}
    assert apply_credential_management(config, "1") == []
    assert config == {"api_key": "direct_value"}


def test_missing_manager_or_fields_returns_empty():
    config = {
        "api_key": "direct_value",
        "_reserved_credential_management": {
            "settings": {"manager": "hashicorp"},
            "fields": [],
        },
    }
    assert apply_credential_management(config, "1") == []
    assert config["api_key"] == "direct_value"


def test_manager_load_failure_raises():
    config = {
        "api_key": "direct_value",
        "_reserved_credential_management": {
            "settings": {"manager": "hashicorp", "config": {}},
            "fields": [{"name": "api_key"}],
        },
    }
    with (
        mock.patch(f"{CM_MODULE}._soar_is_available", True),
        mock.patch(
            f"{CM_MODULE}.importlib.import_module",
            side_effect=ModuleNotFoundError("no module"),
        ),
        pytest.raises(AssetMisconfiguration),
    ):
        apply_credential_management(config, "1")
    assert config["api_key"] == "direct_value"


def test_batch_manager_overrides_configured_values():
    get_credential = mock.Mock(
        return_value=[
            {"name": "api_key", "value": "vault_key"},
            {"name": "api_secret", "value": "vault_secret"},
        ]
    )
    config = {
        "api_key": "direct_key",
        "api_secret": "direct_secret",
        "_reserved_credential_management": {
            "settings": {"manager": "hashicorp", "config": {"url": "https://v"}},
            "fields": [{"name": "api_key"}, {"name": "api_secret"}],
        },
    }
    with mock.patch(
        f"{CM_MODULE}._load_credential_manager", return_value=get_credential
    ):
        resolved = apply_credential_management(config, "1")

    assert sorted(resolved) == ["api_key", "api_secret"]
    assert config["api_key"] == "vault_key"
    assert config["api_secret"] == "vault_secret"
    get_credential.assert_called_once_with(
        [{"name": "api_key"}, {"name": "api_secret"}], {"url": "https://v"}
    )


def test_cyberark_fetches_each_field_individually():
    get_credential = mock.Mock(side_effect=["cyberark_key"])
    config = {
        "api_key": "direct_key",
        "_reserved_credential_management": {
            "settings": {"manager": "cyberark", "config": {"safe": "s"}},
            "fields": [{"name": "api_key"}],
        },
    }
    with mock.patch(
        f"{CM_MODULE}._load_credential_manager", return_value=get_credential
    ):
        resolved = apply_credential_management(config, "1")

    assert resolved == ["api_key"]
    assert config["api_key"] == "cyberark_key"
    get_credential.assert_called_once_with({"name": "api_key"}, {"safe": "s"})


def test_fetch_failure_raises():
    get_credential = mock.Mock(side_effect=RuntimeError("vault down"))
    config = {
        "api_key": "direct_key",
        "_reserved_credential_management": {
            "settings": {"manager": "hashicorp", "config": {}},
            "fields": [{"name": "api_key"}],
        },
    }
    with (
        mock.patch(
            f"{CM_MODULE}._load_credential_manager", return_value=get_credential
        ),
        pytest.raises(AssetMisconfiguration),
    ):
        apply_credential_management(config, "1")


def test_local_mode_returns_empty_without_platform():
    config = {
        "api_key": "direct_key",
        "_reserved_credential_management": {
            "settings": {"manager": "hashicorp", "config": {}},
            "fields": [{"name": "api_key"}],
        },
    }
    with mock.patch(f"{CM_MODULE}._soar_is_available", False):
        assert apply_credential_management(config, "1") == []
    assert config["api_key"] == "direct_key"


def test_handle_skips_decryption_for_managed_field(
    example_app: App, simple_action_input: InputSpecification
):
    class TestAsset(BaseAsset):
        client_id: str = AssetField(sensitive=True)
        client_secret: str = AssetField(sensitive=True)

    example_app.asset_cls = TestAsset

    simple_action_input.config = AppConfig(
        app_version="1.0.0",
        directory=".",
        main_module="example_connector.py",
        client_id="plaintext_from_vault",
        client_secret=encrypt("decrypted_secret", simple_action_input.asset_id),
        _reserved_credential_management={
            "settings": {"manager": "hashicorp", "config": {}},
            "fields": [{"name": "client_id"}],
        },
    )

    get_credential = mock.Mock(
        return_value=[{"name": "client_id", "value": "plaintext_from_vault"}]
    )
    with (
        mock.patch(
            f"{CM_MODULE}._load_credential_manager", return_value=get_credential
        ),
        mock.patch.object(example_app.actions_manager, "handle"),
    ):
        example_app.handle(simple_action_input.model_dump_json())

    # The managed field keeps the plaintext value from the manager (not decrypted),
    # while the unmanaged sensitive field is still decrypted normally.
    assert example_app._raw_asset_config["client_id"] == "plaintext_from_vault"
    assert example_app._raw_asset_config["client_secret"] == "decrypted_secret"
