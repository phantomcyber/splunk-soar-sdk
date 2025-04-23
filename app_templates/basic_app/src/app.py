#!/usr/bin/python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput

app = App()


@app.action(action_type="test")
def test_connectivity(params: Params, client: SOARClient) -> ActionOutput:
    """Testing the connectivity service."""
    client.save_progress("Connectivity checked!")
    return ActionOutput()


if __name__ == "__main__":
    app.cli()
