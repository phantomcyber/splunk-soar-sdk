#!/usr/bin/python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput

app = App()


@app.action(action_type="test")
def test_connectivity(param: Params, client: SOARClient) -> ActionOutput:
    client.debug("params", param.json())
    return ActionOutput()


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(action_type="test")
def reverse_string(
    param: ReverseStringParams, client: SOARClient
) -> ReverseStringOutput:
    client.debug("params", param.json())
    reversed_string = param.input_string[::-1]
    client.debug("reversed_string", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


if __name__ == "__main__":
    app.run()
