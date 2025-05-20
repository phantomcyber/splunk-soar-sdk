#public interface for the vault. There will also be a shim which it uses to deal
from soar_sdk.shims.phantom.vault import Vault as PhantomVault

class Vault(PhantomVault):
    """
    Vault class to handle file attachments.
    """
    
    #ccan create an authenticated client here

    def _add_attachment(self, file_location: str, container_id: int, file_name: str = None, metadata: dict[str, str] = None) -> dict:
        """
        Add an attachment to vault.
        """
        # Placeholder implementation
        return {"status": "success", "container_id": container_id}