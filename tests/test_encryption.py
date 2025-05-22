import base64
from soar_sdk.shims.phantom.encryption_helper import encryption_helper
from soar_sdk.crypto import Encryption


def test_encryption_helper_not_available():
    # Test the behavior when the EncryptionHelper is not available

    assert encryption_helper.encrypt("test_string", "unused") == base64.b64encode(
        b"test_string"
    ).decode("utf-8")
    assert encryption_helper.decrypt("dGVzdHN0cmluZw==", "") == "teststring"
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_", ""), "")
        == "test_string_"
    )


def test_crypto():
    # Test encryption
    encrypted_text = Encryption.encrypt("test_string")
    assert encrypted_text == base64.b64encode(b"test_string").decode("utf-8")

    # Test decryption
    decrypted_text = Encryption.decrypt(encrypted_text)
    assert decrypted_text == "test_string"
