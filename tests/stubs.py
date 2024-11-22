from unittest import mock

from soar_sdk.params import Param, Params


class SampleActionParams(Params):
    field1: int = Param(0, "Some description")


class BaseConnectorMock(mock.Mock):
    mocked_methods = [
        "_get_phantom_base_url",
        "_set_csrf_info",
        "handle_action",
        "_handle_action",
        "initialize",
        "finalize",
        "add_action_result",
        "get_action_results",
        "save_progress",
        "debug_print",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # mocking all BaseConnector methods
        for method_name in self.mocked_methods:
            setattr(self, method_name, mock.MagicMock())
