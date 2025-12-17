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

    def get_all(self, *, force_reload: bool = False) -> AssetStateType:
        """Get the entirety of this part of the asset state."""
        if force_reload:
            self.backend.reload_state_from_file(self.asset_id)
        state = self.backend.load_state() or {}
        if not (part_encrypted := state.get(self.state_key)):
            return {}
        part_json = encryption_helper.decrypt(part_encrypted, self.asset_id)
        return json.loads(part_json)

    def put_all(self, new_value: AssetStateType) -> None:
        """Entirely replace this part of the asset state."""
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
