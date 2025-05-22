import base64


def test_encryption_helper_not_available():
    # Test the behavior when the EncryptionHelper is not available
    from soar_sdk.shims.phantom.encryption_helper import encryption_helper

    assert encryption_helper.encrypt("test_string", "unused") == base64.b64encode(
        b"test_string"
    ).decode("utf-8")
    assert encryption_helper.decrypt("dGVzdHN0cmluZw==", "") == "teststring"
    assert (
        encryption_helper.decrypt(encryption_helper.encrypt("test_string_", ""), "")
        == "test_string_"
    )
