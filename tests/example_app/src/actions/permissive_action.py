from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.params import Params

logger = getLogger()


class PermissiveReverseStringParams(Params):
    input_string: str


class NestedOutput(ActionOutput):
    foo: int
    bar: int


class PermissiveReverseStringOutput(PermissiveActionOutput):
    original_string: str
    reversed_string: str
    underscored_string: str = OutputField(alias="_underscored_string")
    nested_output: NestedOutput


def permissive_reverse_string(
    param: PermissiveReverseStringParams, soar: SOARClient
) -> PermissiveReverseStringOutput:
    logger.debug("params: %s", param)
    reversed_string = param.input_string[::-1]
    logger.debug("reversed_string %s", reversed_string)
    soar.set_message(f"Reversed string: {reversed_string}")
    return PermissiveReverseStringOutput(
        **{
            "original_string": "testing",
            "reversed_string": "gnitset",
            "nested_output": {"foo": 3},
        }
    )
