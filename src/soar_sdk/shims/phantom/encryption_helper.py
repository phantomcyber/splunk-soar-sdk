try:
    import encryption_helper  # type: ignore[import-not-found]

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    import base64

    class encryption_helper:  # type: ignore[no-redef]
        """Simulated encryption helper for environments without BaseConnector."""

        @staticmethod
        def encrypt(plain: str, salt: str) -> str:
            """Simulates the behavior of encryption_helper.encrypt."""
            salted = plain + ":" + salt
            return base64.b64encode(salted.encode("utf-8")).decode("utf-8")

        @staticmethod
        def decrypt(cipher: str, salt: str) -> str:
            """Simulate the behavior of encryption_helper.decrypt."""
            decoded = base64.b64decode(cipher.encode("utf-8")).decode("utf-8")
            plain, decrypted_salt = decoded.split(":", 1)
            if salt != decrypted_salt:
                raise ValueError("Salt does not match")
            return plain


__all__ = ["encryption_helper"]
