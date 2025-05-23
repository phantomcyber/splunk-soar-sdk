from unittest import mock

from soar_sdk.adapters import LegacyConnectorAdapter
from tests.stubs import BaseConnectorMock
import pytest


def test_legacy_connector_adapter_delegates_method_calls():
    adapter = LegacyConnectorAdapter(BaseConnectorMock)

    adapter.get_soar_base_url()
    adapter.get_product_installation_id()
    adapter.set_csrf_info(mock.Mock(), mock.Mock())
    adapter.handle(mock.Mock())
    adapter.handle_action(mock.Mock())
    adapter.initialize()
    adapter.finalize()
    adapter.add_result(mock.Mock())
    adapter.get_results()
    adapter.save_progress(mock.Mock())
    adapter.debug(mock.Mock())
    adapter.error(mock.Mock())
    adapter.add_exception(mock.Mock())
    adapter.update_client(mock.Mock())
    with pytest.raises(NotImplementedError):
        adapter.get(mock.Mock())
    with pytest.raises(NotImplementedError):
        adapter.post(mock.Mock())
    with pytest.raises(NotImplementedError):
        adapter.put(mock.Mock())
    with pytest.raises(NotImplementedError):
        adapter.delete(mock.Mock())
    with pytest.raises(NotImplementedError):
        _ = adapter.client
    with pytest.raises(NotImplementedError):
        _ = adapter.container
    with pytest.raises(NotImplementedError):
        _ = adapter.artifact
    with pytest.raises(NotImplementedError):
        _ = adapter.vault

    for method_name in adapter.connector.mocked_methods:
        mocked_method = getattr(adapter.connector, method_name)
        mocked_method.assert_called_once()
