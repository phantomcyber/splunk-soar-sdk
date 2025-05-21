import base64
from soar_sdk.shims.phantom.encryption_helper import (
    EncryptionHelper as encryption_helper,
)


def test_encryption_helper_not_available():
    # Check that the encrypt and decrypt functions are shimmed correctly
    assert encryption_helper.encrypt("test_string") == base64.b64encode(
        b"test_string"
    ).decode("utf-8")
    assert encryption_helper.decrypt("dGVzdHN0cmluZw==") == "teststring"
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_"))
        == "test_string_"
    )
