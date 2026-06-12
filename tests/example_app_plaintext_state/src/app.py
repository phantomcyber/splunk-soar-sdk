from pathlib import Path

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.app import App
from soar_sdk.asset import BaseAsset
from soar_sdk.logging import getLogger
from soar_sdk.params import Params

logger = getLogger()

APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf57"
APP_STATE_DIRECTORY = Path("/opt/phantom/var/splunk_data/local_data/app_states")
AUTH_FILESYSTEM_MARKER = "papp-37866-auth-filesystem-marker"
CACHE_FILESYSTEM_MARKER = "papp-37866-cache-filesystem-marker"
INGEST_FILESYSTEM_MARKER = "papp-37866-ingest-filesystem-marker"


class Asset(BaseAsset):
    base_url: str


app = App(
    asset_cls=Asset,
    name="example_app_plaintext_state",
    appid=APP_ID,
    app_type="sandbox",
    product_vendor="Splunk Inc.",
    logo="logo.svg",
    logo_dark="logo_dark.svg",
    product_name="Example Plaintext State App",
    publisher="Splunk Inc.",
    min_phantom_version="6.2.2.134",
    encrypt_cache_state=False,
    encrypt_ingest_state=False,
)


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    logger.info(f"testing connectivity against {asset.base_url}")


class FilesystemStateOutput(ActionOutput):
    state_file_path: str
    raw_state_json: str


def _asset_state_file_path(soar: SOARClient) -> Path:
    return APP_STATE_DIRECTORY / APP_ID / f"{soar.get_asset_id()}_state.json"


@app.action(read_only=False)
def write_filesystem_state(
    params: Params, soar: SOARClient, asset: Asset
) -> ActionOutput:
    asset.auth_state.put_all({"auth_marker": AUTH_FILESYSTEM_MARKER})
    asset.cache_state.put_all({"cache_marker": CACHE_FILESYSTEM_MARKER})
    asset.ingest_state.put_all({"ingest_marker": INGEST_FILESYSTEM_MARKER})
    return ActionOutput()


@app.action()
def read_filesystem_state(params: Params, soar: SOARClient) -> FilesystemStateOutput:
    state_file_path = _asset_state_file_path(soar)
    return FilesystemStateOutput(
        state_file_path=str(state_file_path),
        raw_state_json=state_file_path.read_text(encoding="utf-8"),
    )


if __name__ == "__main__":
    app.cli()
