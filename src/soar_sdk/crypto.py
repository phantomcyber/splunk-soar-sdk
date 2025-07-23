from soar_sdk.shims.phantom.encryption_helper import encryption_helper


def encrypt(plain: str, salt: str) -> str:
    """Encrypts the given plain text with the provided salt."""
    return encryption_helper.encrypt(plain, salt)


def decrypt(cipher: str, salt: str) -> str:
    """Decrypts the given cipher text with the provided salt."""
    return encryption_helper.decrypt(cipher, salt)
