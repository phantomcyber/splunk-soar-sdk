import base64
from unittest import mock


def test_encryption_helper_not_available():
    # Test the behavior when the EncryptionHelper is not available
    from soar_sdk.shims.phantom.encryption_helper import (
        EncryptionHelper as encryption_helper,
    )

    assert encryption_helper.encrypt("test_string") == base64.b64encode(
        b"test_string"
    ).decode("utf-8")
    assert encryption_helper.decrypt("dGVzdHN0cmluZw==") == "teststring"
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_"))
        == "test_string_"
    )


def test_encryption_helper_phantom_available():
    # Test the behavior when the EncryptionHelper is available
    class MockEncryptionHelper:
        @staticmethod
        def encrypt(plain: str, salt: str = "") -> str:
            return "mocked_encrypted"

        @staticmethod
        def decrypt(cipher: str, salt: str = "") -> str:
            return "mocked_decrypted"

    with mock.patch(
        "soar_sdk.shims.phantom.encryption_helper.EncryptionHelper",
        MockEncryptionHelper,
    ):
        # Re-import the class to pick up the mocked version
        from soar_sdk.shims.phantom.encryption_helper import EncryptionHelper

        assert EncryptionHelper.encrypt("test_string") == "mocked_encrypted"
        assert EncryptionHelper.decrypt("test_string") == "mocked_decrypted"
