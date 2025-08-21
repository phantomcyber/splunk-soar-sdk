from typing import ClassVar
from unittest import mock

from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Param, Params


class SampleActionParams(Params):
    field1: int = Param(0, "Some description")


class BaseConnectorMock(mock.Mock):
    mocked_methods: ClassVar[list[str]] = [
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
        "get_product_installation_id",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # mocking all BaseConnector methods
        for method_name in self.mocked_methods:
            setattr(self, method_name, mock.MagicMock())


class SampleNestedOutput(ActionOutput):
    bool_value: bool


class SampleOutput(ActionOutput):
    string_value: str
    int_value: int
    list_value: list[str]
    bool_value: bool
    nested_value: SampleNestedOutput
