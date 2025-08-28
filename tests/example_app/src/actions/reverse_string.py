from soar_sdk.logging import getLogger
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Params

logger = getLogger()


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    def generate_action_summary_message(self) -> str:
        return f"Reversed string: {self.reversed_string}"

    original_string: str
    reversed_string: str
    underscored_string: str = OutputField(alias="_underscored_string")


def reverse_string(param: ReverseStringParams, soar: SOARClient) -> ReverseStringOutput:
    logger.debug("params: %s", param)
    reversed_string = param.input_string[::-1]
    logger.debug("reversed_string %s", reversed_string)
    return ReverseStringOutput(
        original_string=param.input_string,
        reversed_string=reversed_string,
        underscored_string=f"{param.input_string}_{reversed_string}",
    )


def render_reverse_string_view(output: list[ReverseStringOutput]) -> dict:
    return {
        "original": output[0].original_string,
        "reversed": output[0].reversed_string,
    }
