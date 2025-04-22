from unittest import mock

from soar_sdk.adapters import LegacyConnectorAdapter
from tests.stubs import BaseConnectorMock


def test_legacy_connector_adapter_delegates_method_calls():
    adapter = LegacyConnectorAdapter(BaseConnectorMock)

    adapter.get_soar_base_url()
    adapter.set_csrf_info(mock.Mock(), mock.Mock())
    adapter.handle(mock.Mock())
    adapter.handle_action(mock.Mock())
    adapter.initialize()
    adapter.finalize()
    adapter.add_result(mock.Mock())
    adapter.get_results()
    adapter.save_progress(mock.Mock())
    adapter.debug(mock.Mock())

    for method_name in adapter.connector.mocked_methods:
        mocked_method = getattr(adapter.connector, method_name)
        mocked_method.assert_called_once()
