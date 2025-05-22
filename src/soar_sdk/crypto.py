from soar_sdk.shims.phantom.encryption_helper import encryption_helper


class Encryption:
    """
    Encryption class to handle encryption and decryption of data.
    """

    @staticmethod
    def encrypt(plain: str) -> str:
        """
        Encrypts the given plain text

        Args:
            plain (str): The plain text to encrypt.

        Returns:
            str: The encrypted text.
        """
        return encryption_helper.encrypt(plain, "")

    @staticmethod
    def decrypt(cipher: str) -> str:
        """
        Decrypts the given cipher text

        Args:
            cipher (str): The cipher text to decrypt.

        Returns:
            str: The decrypted text.
        """
        return encryption_helper.decrypt(cipher, "")
