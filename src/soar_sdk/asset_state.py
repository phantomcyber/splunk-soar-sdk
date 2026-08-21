import json
from collections.abc import Iterator, MutableMapping
from typing import Any

from soar_sdk.logging import getLogger
from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.shims.phantom.encryption_helper import encryption_helper

AssetStateKeyType = str
AssetStateValueType = Any
AssetStateType = dict[AssetStateKeyType, AssetStateValueType]

logger = getLogger()


def _decode_json_object(value: str) -> AssetStateType | None:
    """Decode a JSON object, or None if the value is not one."""
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


class AssetState(MutableMapping[AssetStateKeyType, AssetStateValueType]):
    """An adapter to one partition of asset state stored within SOAR.

    State is encrypted at rest by default. On installs which encrypt the asset
    state on the app's behalf, such as RPC automation brokers, it is stored
    as-is.

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
        """Decode a stored part of the asset state, encrypted or not.

        Some installs, such as RPC automation brokers, provide an encryption
        helper which returns values unchanged, so a stored part may be
        plaintext, or ciphertext this install holds no key for. State that
        cannot be read is discarded instead of failing the action.
        """
        try:
            candidates = (encryption_helper.decrypt(part, self.asset_id), part)
        except Exception as e:
            # Encryption helpers differ per install type. Some raise on values
            # they did not encrypt, and others return them unchanged.
            logger.debug(f"Could not decrypt {self.state_key} state: {e}")
            candidates = (part,)

        for candidate in candidates:
            if (decoded := _decode_json_object(candidate)) is not None:
                return decoded

        logger.warning(f"Discarding unreadable {self.state_key} state")
        return {}

    def _encode_part(self, part_json: str) -> str | AssetStateType:
        """Encrypt a part of the asset state, if encryption is available."""
        if not self.encrypted:
            return json.loads(part_json)

        try:
            encrypted = encryption_helper.encrypt(part_json, salt=self.asset_id)
        except Exception as e:
            logger.debug(f"Could not encrypt {self.state_key} state: {e}")
            encrypted = part_json

        if encrypted == part_json:
            # The encryption helper is a no-op on this install, such as an RPC
            # automation broker, where SOAR encrypts the asset state at rest
            # instead. Store the mapping itself, which stays readable on every
            # install, rather than a string which only looks encrypted.
            return json.loads(part_json)
        return encrypted

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
