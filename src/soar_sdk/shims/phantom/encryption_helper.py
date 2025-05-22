try:
    import encryption_helper  # type: ignore[import-not-found]

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    import base64

    class encryption_helper:  # type: ignore[no-redef]
        @staticmethod
        def encrypt(plain: str, salt: str) -> str:
            """Simulates the behavior of encryption_helper.encrypt."""
            return base64.b64encode(plain.encode("utf-8")).decode("utf-8")

        @staticmethod
        def decrypt(cipher: str, salt: str) -> str:
            """Simulate the behavior of encryption_helper.decrypt."""
            return base64.b64decode(cipher.encode("utf-8")).decode("utf-8")


__all__ = ["encryption_helper"]
