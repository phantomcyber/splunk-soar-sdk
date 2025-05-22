from soar_sdk.shims.phantom.encryption_helper import encryption_helper


class Encryption:
    """
    Encryption class to handle encryption and decryption of data.
    """

    @staticmethod
    def encrypt(plain: str) -> str:
        # Encrypts the given plain text
        return encryption_helper.encrypt(plain, "")

    @staticmethod
    def decrypt(cipher: str) -> str:
        # Decrypts the given cipher text
        return encryption_helper.decrypt(cipher, "")
