try:
    from phantom_common.encryption.encryption_manager_factory import (
        platform_encryption_backend,
    )

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    from soar_sdk.shims.phantom.encryption_helper import encryption_helper

    class MockEncryptionBackend:
        def encrypt(self, plain: str, salt: str) -> str:
            return encryption_helper.encrypt(plain, salt)

        def decrypt(self, cipher: str, salt: str) -> str:
            return encryption_helper.decrypt(cipher, salt)

    platform_encryption_backend = MockEncryptionBackend()


__all__ = ["platform_encryption_backend"]
