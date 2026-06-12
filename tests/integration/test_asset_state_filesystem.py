import json

from .soar_client import AppOnStackClient

AUTH_FILESYSTEM_MARKER = "papp-37866-auth-filesystem-marker"
CACHE_FILESYSTEM_MARKER = "papp-37866-cache-filesystem-marker"
INGEST_FILESYSTEM_MARKER = "papp-37866-ingest-filesystem-marker"
STATE_DIRECTORY = "/opt/phantom/var/splunk_data/local_data/app_states"
DEFAULT_APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf55"
PLAINTEXT_APP_ID = "9b388c08-67de-4ca4-817f-26f8fb7cbf57"


def _state_file_path(client: AppOnStackClient, app_id: str) -> str:
    assert client.asset_id is not None
    return f"{STATE_DIRECTORY}/{app_id}/{client.asset_id}_state.json"


def _write_and_read_raw_state_file(
    client: AppOnStackClient, app_id: str
) -> tuple[str, dict]:
    write_result = client.run_action("write filesystem state", {})
    assert write_result.success, (
        f"Filesystem state writing action failed: {write_result.message}"
    )

    read_result = client.run_action("read filesystem state", {})
    assert read_result.success, (
        f"Filesystem state reading action failed: {read_result.message}"
    )

    assert read_result.data is not None
    data = read_result.data["data"][0]
    assert data["state_file_path"] == _state_file_path(client, app_id)
    raw_state_json = data["raw_state_json"]
    return raw_state_json, json.loads(raw_state_json)


def test_default_app_filesystem_state_is_encrypted(
    example_app_client: AppOnStackClient,
):
    raw_state_json, state = _write_and_read_raw_state_file(
        example_app_client, DEFAULT_APP_ID
    )

    assert isinstance(state["auth"], str)
    assert isinstance(state["cache"], str)
    assert isinstance(state["ingest"], str)
    assert AUTH_FILESYSTEM_MARKER not in raw_state_json
    assert CACHE_FILESYSTEM_MARKER not in raw_state_json
    assert INGEST_FILESYSTEM_MARKER not in raw_state_json


def test_plaintext_app_filesystem_state_keeps_cache_and_ingest_readable(
    plaintext_state_app_client: AppOnStackClient,
):
    raw_state_json, state = _write_and_read_raw_state_file(
        plaintext_state_app_client, PLAINTEXT_APP_ID
    )

    assert isinstance(state["auth"], str)
    assert state["cache"] == {"cache_marker": CACHE_FILESYSTEM_MARKER}
    assert state["ingest"] == {"ingest_marker": INGEST_FILESYSTEM_MARKER}
    assert AUTH_FILESYSTEM_MARKER not in raw_state_json
    assert CACHE_FILESYSTEM_MARKER in raw_state_json
    assert INGEST_FILESYSTEM_MARKER in raw_state_json
