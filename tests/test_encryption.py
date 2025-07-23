import base64
from soar_sdk.shims.phantom.encryption_helper import encryption_helper
from soar_sdk import crypto


def test_encryption_helper_not_available():
    # Test the behavior when the EncryptionHelper is not available

    assert encryption_helper.encrypt("test_string", "unused") == base64.b64encode(
        b"test_string:unused"
    ).decode("utf-8")
    assert (
        encryption_helper.decrypt("dGVzdF9zdHJpbmc6dW51c2Vk", "unused") == "test_string"
    )
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_", ""), "")
        == "test_string_"
    )


def test_crypto():
    # Test encryption
    encrypted_text = crypto.encrypt("test_string", "K2SO4")
    assert encrypted_text == base64.b64encode(b"test_string:K2SO4").decode("utf-8")

    # Test decryption
    decrypted_text = crypto.decrypt(encrypted_text, "K2SO4")
    assert decrypted_text == "test_string"
