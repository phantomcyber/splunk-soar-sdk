import json
from collections.abc import Iterator, MutableMapping
from contextlib import suppress
from typing import Any

from soar_sdk.logging import getLogger
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.shims.phantom.encryption_helper import encryption_helper
from soar_sdk.shims.phantom.install_info import is_onprem_broker_rpc_install

AssetStateKeyType = str
AssetStateValueType = Any
AssetStateType = dict[AssetStateKeyType, AssetStateValueType]

logger = getLogger()


class AssetState(MutableMapping[AssetStateKeyType, AssetStateValueType]):
    """An adapter to one partition of asset state stored within SOAR.

    State is encrypted at rest by default. On RPC automation brokers, where SOAR
    encrypts the asset state on the app's behalf, it is stored as-is.

    Unencrypted asset state can be useful if you intend for users to read or
    edit the asset state directly from the filesystem, outside of SOAR. Please
    note that this use case is not officially supported, and a future version of
    SOAR will begin storing the asset state in the database instead of the
    filesystem.
    """

    def __init__(
        self,
        backend: BaseConnector,
        state_key: str,
        asset_id: str,
        app_id: str | None = None,
        encrypted: bool = True,
    ) -> None:
        self.backend = backend
        self.state_key = state_key
        self.asset_id = asset_id
        self.app_id = app_id
        self.encrypted = encrypted
        self._transaction_buffer: AssetStateType | None = None

    @property
    def in_transaction(self) -> bool:
        """Whether a transaction is currently active."""
        return self._transaction_buffer is not None

    def begin_transaction(self) -> None:
        """Begin a transaction. Writes are buffered until commit() is called."""
        if self.in_transaction:
            raise RuntimeError("Transaction already active")
        self._transaction_buffer = self.get_all()

    def commit(self) -> None:
        """Flush buffered writes to the backend."""
        if self._transaction_buffer is None:
            raise RuntimeError("No active transaction")
        buffered = self._transaction_buffer
        self._transaction_buffer = None
        try:
            self.put_all(buffered)
        except Exception:
            self._transaction_buffer = buffered
            raise

    def rollback(self) -> None:
        """Discard buffered writes."""
        if not self.in_transaction:
            raise RuntimeError("No active transaction")
        self._transaction_buffer = None

    def get_all(self, *, force_reload: bool = False) -> AssetStateType:
        """Get the entirety of this part of the asset state."""
        if self._transaction_buffer is not None:
            return dict(self._transaction_buffer)
        if force_reload:
            # backend is from phantom_common shim, whose imports are replaced with Any
            self.backend.reload_state_from_file(  # ty: ignore[unresolved-attribute]
                self.asset_id
            )
        state = self.backend.load_state() or {}
        if not (part := state.get(self.state_key)):
            return {}
        if isinstance(part, dict):
            return dict(part)
        return self._decode_part(part)

    def put_all(self, new_value: AssetStateType) -> None:
        """Entirely replace this part of the asset state."""
        if self.in_transaction:
            self._transaction_buffer = dict(new_value)
            return
        state = self.backend.load_state() or {}
        state[self.state_key] = self._encode_part(json.dumps(new_value))
        self.backend.save_state(state)

    def _decode_part(self, part: str) -> AssetStateType:
        """Decode a stored part of the asset state, decrypting it if needed.

        A part stored on an RPC automation broker is either plaintext or
        ciphertext this install holds no key for, so state which cannot be read
        is discarded instead of failing the action.
        """
        if not is_onprem_broker_rpc_install():
            return json.loads(encryption_helper.decrypt(part, self.asset_id))

        decoded = None
        with suppress(json.JSONDecodeError):
            decoded = json.loads(part)
        if isinstance(decoded, dict):
            return decoded

        logger.error(f"Discarding unreadable {self.state_key} state")
        return {}

    def _encode_part(self, part_json: str) -> str | AssetStateType:
        """Encode a part of the asset state, encrypting it if needed.

        RPC automation brokers store the mapping as-is, since SOAR encrypts the
        asset state at rest on their behalf.
        """
        if not self.encrypted or is_onprem_broker_rpc_install():
            return json.loads(part_json)

        return encryption_helper.encrypt(part_json, salt=self.asset_id)

    def __getitem__(self, key: AssetStateKeyType) -> AssetStateValueType:
        return self.get_all()[key]

    def __setitem__(self, key: AssetStateKeyType, value: AssetStateValueType) -> None:
        s = self.get_all()
        s[key] = value
        self.put_all(s)

    def __delitem__(self, key: AssetStateKeyType) -> None:
        s = self.get_all()
        del s[key]
        self.put_all(s)

    def __iter__(self) -> Iterator[AssetStateKeyType]:
        yield from self.get_all().keys()

    def __len__(self) -> int:
        return len(self.get_all().keys())
