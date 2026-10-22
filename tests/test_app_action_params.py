from unittest import mock

import pytest

from soar_sdk.action_results import ActionOutput
from soar_sdk.app import App
from soar_sdk.input_spec import AppConfig, InputSpecification
from soar_sdk.params import Param, Params
from tests.stubs import SampleActionParams


class SensitiveParams(Params):
    password: str = Param(description="Password", sensitive=True)
    username: str = Param(description="Username")


def test_app_action_run_use_empty_params_definition(example_app: App):
    @example_app.action()
    def foo(params: Params, client) -> ActionOutput:
        assert True

    foo(Params())


def test_app_action_run_define_params_class_in_decorator(example_app: App):
    @example_app.action(params_class=SampleActionParams)
    def foo(params, client) -> ActionOutput:
        assert True

    foo(SampleActionParams())


def test_app_action_run_use_params_model(example_app):
    @example_app.action()
    def foo(params: SampleActionParams, client) -> ActionOutput:
        assert params.field1 == 5

    foo(SampleActionParams(field1=5))


def test_app_action_handling_simple_params_conversion(example_app: App):
    @example_app.action()
    def foo(params: SampleActionParams, client) -> ActionOutput:
        assert params.field1 == 5

    with mock.patch.object(
        example_app.actions_manager,
        "get_action_identifier",
        return_value="foo",
    ):
        example_app.actions_manager.handle_action({"field1": 5})


def test_app_action_handling_validation_error_raised(example_app: App):
    @example_app.action(params_class=SampleActionParams)
    def foo(params: SampleActionParams, client) -> ActionOutput:
        assert params.field1 == 5

    with mock.patch.object(
        example_app.actions_manager,
        "get_action_identifier",
        return_value="foo",
    ):
        example_app.actions_manager.handle_action({"field1": "five"})


def test_handle_action_decrypts_sensitive_params(example_app: App):
    """Sensitive params are decrypted before being passed to the action."""
    received: dict = {}

    @example_app.action()
    def secret_action(params: SensitiveParams) -> ActionOutput:
        received["password"] = params.password
        received["username"] = params.username
        return ActionOutput()

    example_app.actions_manager._enable_action_param_encryption = True
    example_app.actions_manager._action_param_dec_key = "test_key"

    with (
        mock.patch(
            "soar_sdk.actions_manager.platform_encryption_backend.decrypt",
            side_effect=lambda val, key: f"decrypted:{val}",
        ),
        mock.patch.object(
            example_app.actions_manager,
            "get_action_identifier",
            return_value="secret_action",
        ),
    ):
        example_app.actions_manager.handle_action(
            {"password": "ciphertext", "username": "alice"}
        )

    assert received["password"] == "decrypted:ciphertext"
    assert received["username"] == "alice"


def test_handle_action_skips_decryption_when_flag_false(example_app: App):
    """Params are not decrypted when enable_action_parameter_encryption is False."""
    received: dict = {}

    @example_app.action()
    def secret_action2(params: SensitiveParams) -> ActionOutput:
        received["password"] = params.password
        return ActionOutput()

    example_app.actions_manager._enable_action_param_encryption = False
    example_app.actions_manager._action_param_dec_key = "test_key"

    with (
        mock.patch(
            "soar_sdk.actions_manager.platform_encryption_backend.decrypt"
        ) as mock_decrypt,
        mock.patch.object(
            example_app.actions_manager,
            "get_action_identifier",
            return_value="secret_action2",
        ),
    ):
        example_app.actions_manager.handle_action(
            {"password": "ciphertext", "username": "alice"}
        )

    mock_decrypt.assert_not_called()
    assert received["password"] == "ciphertext"


def test_handle_stores_encryption_flag_from_input(example_app: App):
    """handle() propagates enable_action_parameter_encryption and dec_key to instance state."""

    @example_app.action()
    def test_action(params: Params) -> ActionOutput:
        return ActionOutput()

    input_data = InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        enable_action_parameter_encryption=True,
        dec_key="test_key",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
    )

    with mock.patch.object(example_app.actions_manager, "_handle_action"):
        example_app.actions_manager.handle(input_data)

    assert example_app.actions_manager._enable_action_param_encryption is True
    assert example_app.actions_manager._action_param_dec_key == "test_key"


@pytest.mark.parametrize("value", ["already-decrypted", "", "iv:literal-password"])
def test_native_plaintext_is_never_decrypted_again(example_app, value):
    received = []

    @example_app.action()
    def native_secret(params: SensitiveParams) -> ActionOutput:
        received.append(params.password)
        return ActionOutput()

    example_app.actions_manager._enable_action_param_encryption = True
    example_app.actions_manager._action_param_dec_key = "test_key"
    with (
        mock.patch(
            "soar_sdk.actions_manager._uses_platform_base_connector", True, create=True
        ),
        mock.patch(
            "soar_sdk.actions_manager.platform_encryption_backend.decrypt",
            side_effect=AssertionError("Native plaintext must not be decrypted again"),
        ) as decrypt,
        mock.patch.object(
            example_app.actions_manager,
            "get_action_identifier",
            return_value="native_secret",
        ),
    ):
        example_app.actions_manager.handle_action(
            {"password": value, "username": "alice"}
        )
    assert received == [value]
    decrypt.assert_not_called()


def test_fallback_full_dispatch_decrypts_aliased_sensitive_fields(example_app):
    from soar_sdk.shims.phantom_common.encryption.encryption_manager_factory import (
        platform_encryption_backend,
    )

    class AliasedSecrets(Params):
        secret: str = Param(
            description="Secret", alias="external_secret", sensitive=True
        )
        username: str = Param(description="Username")

    received = []

    @example_app.action()
    def aliased_secret(params: AliasedSecrets) -> ActionOutput:
        received.append((params.secret, params.username))
        return ActionOutput()

    key = "test_key"
    input_data = InputSpecification(
        identifier="aliased_secret",
        enable_action_parameter_encryption=True,
        dec_key=key,
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
        parameters=[
            {
                "external_secret": platform_encryption_backend.encrypt(value, key),
                "username": name,
            }
            for value, name in [("first-secret", "alice"), ("second-secret", "bob")]
        ],
    )
    example_app.actions_manager.handle(input_data)
    assert received == [("first-secret", "alice"), ("second-secret", "bob")]
