from soar_sdk.action_group import ActionGroup
from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Params
from soar_sdk.abstract import SOARClient
from soar_sdk.logging import getLogger
import logging
logger = getLogger() 

action_group = ActionGroup(name="test")

class TestParams(Params):
    category: str

#@action_group.action(name="test_action", description="A test action")
#def test_action(params: TestParams) -> ActionOutput:
#    return ActionOutput()


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@action_group.action(action_type="test", verbose="Reverses a string.")
def reverse_string(param: ReverseStringParams, soar: SOARClient) -> ReverseStringOutput:
    soar.get("rest/version")
    logger.debug("params: %s", param)
    reversed_string = param.input_string[::-1]
    logger.debug("reversed_string %s", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


class ReverseStringViewOutput(ActionOutput):
    original_string: str
    reversed_string: str


@action_group.view_handler(template="reverse_string.html")
def render_reverse_string_view(output: list[ReverseStringViewOutput]) -> dict:
    return {
        "original": output[0].original_string,
        "reversed": output[0].reversed_string,
    }


@action_group.action(
    action_type="investigate",
    verbose="Reverses a string.",
    view_handler=render_reverse_string_view,
)
def reverse_string_custom_view(
    param: ReverseStringParams, soar: SOARClient
) -> ReverseStringViewOutput:
    reversed_string = param.input_string[::-1]
    return ReverseStringViewOutput(
        original_string=param.input_string, reversed_string=reversed_string
    )

__all__ = ["action_group"]
    