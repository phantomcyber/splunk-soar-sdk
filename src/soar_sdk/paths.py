import os
from pathlib import Path

SDK_ROOT = Path(__file__).parent

# View templates (built into the SDK)
SDK_TEMPLATES = SDK_ROOT / "templates"

# App's templates
APP_TEMPLATES = Path("templates")

APP_INIT_TEMPLATES = SDK_ROOT / "app_templates"

# SOAR platform root (consistent with phantom_common/paths.py)
_PHANTOM_HOME = Path(os.getenv("PHANTOM_HOME", "/opt/phantom"))

PHANTOM_VAULT_TMP = _PHANTOM_HOME / "vault" / "tmp"


def get_asset_state_file(app_id: str, asset_id: str) -> Path:
    """Get the state file path for an asset."""
    return (
        _PHANTOM_HOME / "local_data" / "app_states" / app_id / f"{asset_id}_state.json"
    )
