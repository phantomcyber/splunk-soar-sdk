try:
    from phantom import encryption_helper

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    import base64

    def encrypt(encrypt_input: str) -> str:
        """Mock function to simulate the behavior of encryption_helper.encrypt."""
        return base64.b64encode(encrypt_input.encode("utf-8")).decode("utf-8")

    def decrypt(decrypt_input: str) -> str:
        """Mock function to simulate the behavior of encryption_helper.decrypt."""
        return base64.b64decode(decrypt_input.encode("utf-8")).decode("utf-8")


def encrypt(encrypt_input: str) -> str:  # type: ignore[no-redef]
    """Returns an encrypted string"""
    return encryption_helper.encrypt(encrypt_input)


def decrypt(decrypt_input: str) -> str:  # type: ignore[no-redef]
    """Returns a decrypted string"""
    return encryption_helper.decrypt(decrypt_input)


__all__ = ["decrypt", "encrypt"]
