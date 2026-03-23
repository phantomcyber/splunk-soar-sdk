import json
from collections.abc import Iterator, MutableMapping
from typing import Any

from soar_sdk.shims.phantom.base_connector import BaseConnector
from soar_sdk.shims.phantom.encryption_helper import encryption_helper

AssetStateKeyType = str
AssetStateValueType = Any
AssetStateType = dict[AssetStateKeyType, AssetStateValueType]


class AssetState(MutableMapping[AssetStateKeyType, AssetStateValueType]):
    """An adapter to the asset state stored within SOAR. The state can be split into multiple partitions; this object represents a single partition. State is automatically encrypted at rest."""

    def __init__(
        self,
        backend: BaseConnector,
        state_key: str,
        asset_id: str,
        app_id: str | None = None,
    ) -> None:
        self.backend = backend
        self.state_key = state_key
        self.asset_id = asset_id
        self.app_id = app_id
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
        self.put_all(buffered)

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
        if not (part_encrypted := state.get(self.state_key)):
            return {}
        part_json = encryption_helper.decrypt(part_encrypted, self.asset_id)
        return json.loads(part_json)

    def put_all(self, new_value: AssetStateType) -> None:
        """Entirely replace this part of the asset state."""
        if self.in_transaction:
            self._transaction_buffer = dict(new_value)
            return
        part_json = json.dumps(new_value)
        part_encrypted = encryption_helper.encrypt(part_json, salt=self.asset_id)
        state = self.backend.load_state() or {}
        state[self.state_key] = part_encrypted
        self.backend.save_state(state)

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
