try:
    from phantom import json_keys

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:

    class JsonKeyShim:
        APP_JSON_LABEL = "label"
        APP_JSON_INGEST_APP_ID = "ingest_app_id"
        APP_JSON_DESCRIPTION = "description"
        APP_JSON_RUN_AUTOMATION = "run_automation"
        APP_JSON_TYPE = "type"
        APP_JSON_ASSET_ID = "asset_id"

    json_keys = JsonKeyShim()

__all__ = ["json_keys"]
