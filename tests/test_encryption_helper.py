import sys
import base64
from unittest import mock


def test_mocked_encryption_helper():
    with mock.patch("phantom.encryption_helper") as mock_encryption_helper:
        # Mock the encrypt and decrypt functions
        mock_encryption_helper.encrypt.return_value = "encrypted_value"
        mock_encryption_helper.decrypt.return_value = "decrypted_value"

        # Import the encryption_helper shim
        import soar_sdk.shims.phantom.encryption_helper as encryption_helper

        encrypted_value = encryption_helper.encrypt("test_string")
        decrypted_value = encryption_helper.decrypt("test_string")
        assert encrypted_value == "encrypted_value"
        assert decrypted_value == "decrypted_value"

    # Check that the encrypt and decrypt functions were called
    mock_encryption_helper.encrypt.assert_called_once_with("test_string")
    mock_encryption_helper.decrypt.assert_called_once_with("test_string")


def test_encryption_helper_not_available():
    # Simulate the absence of phantom.encryption_helper
    sys.modules["phantom.encryption_helper"] = None

    # Import the encryption_helper shim
    import soar_sdk.shims.phantom.encryption_helper as encryption_helper

    # Check that the encrypt and decrypt functions are shimmed correctly
    assert encryption_helper.encrypt("test_string") == base64.b64encode(
        b"test_string"
    ).decode("utf-8")
    assert encryption_helper.decrypt("dGVzdHN0cmluZw==") == "teststring"
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_"))
        == "test_string_"
    )
