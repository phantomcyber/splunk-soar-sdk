#!/usr/bin/python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput

app = App(
    name="basic_app",
    appid="1e1618e7-2f70-4fc0-916a-f96facc2d2e4",
    app_type="sandbox",
    product_vendor="Splunk",
    logo="logo.svg",
    logo_dark="logo_dark.svg",
    product_name="Example App",
    publisher="Splunk",
)


@app.action(action_type="test")
def test_connectivity(params: Params, client: SOARClient) -> ActionOutput:
    """Testing the connectivity service."""
    client.save_progress("Connectivity checked!")
    return ActionOutput()


if __name__ == "__main__":
    app.cli()
