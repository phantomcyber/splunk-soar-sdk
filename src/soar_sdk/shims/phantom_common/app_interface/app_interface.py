try:
    from phantom_common.app_interface.app_interface import SoarRestClient

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:
    import requests

    class SoarRestClient:  # type: ignore[no-redef]
        def __init__(self, token: str, asset_id: int) -> None:
            self.asset_id = asset_id
            self.base_url = "https://localhost:9999"

            self.session = requests.Session()
            self.session.headers.update({"Cookie": f"sessionid={token}"})

            self.is_authenticated = bool(token)


__all__ = ["SoarRestClient"]
