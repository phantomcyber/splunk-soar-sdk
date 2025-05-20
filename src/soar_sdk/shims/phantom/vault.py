try:
    from phantom.vault import Vault

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

    from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    from abc import abstractmethod

    class Vault:
        @classmethod
        def get_vault_tmp_dir(cls):
            return "opt/phantom/vault/tmp"

        @abstractmethod
        def _add_attachment(
            cls,
            file_location: str,
            container_id: int,
            file_name: str = None,
            metadata: dict[str, str] = None,
        ) -> dict:
            """
            Add an attachment to vault.
            """
            return True

        def add_attachment(
            cls,
            file_location: str,
            container_id: int,
            file_name: str = None,
            metadata: dict[str, str] = None,
        ) -> dict:
            """
            Add an attachment to vault.
            """
            cls._add_attachment(file_location, container_id, file_name, metadata)


__all__ = ["Vault"]
