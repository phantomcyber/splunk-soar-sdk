from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Params


def importable_action(params: Params) -> ActionOutput:
    """Used by test_action_registration to test action registration via import paths."""
    return ActionOutput()


def importable_view_handler(output: list[ActionOutput]) -> dict:
    """Used by tests to verify view registration via import paths."""
    return {"data": "test_data"}
