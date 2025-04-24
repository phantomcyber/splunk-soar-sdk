#!/usr/bin/python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput


class Asset(BaseAsset):
    base_url: str
    api_key: str = AssetField(sensitive=True, description="API key for authentication")
    key_header: str = AssetField(
        default="Authorization",
        value_list=["Authorization", "X-API-Key"],
        description="Header for API key authentication",
    )


app = App(asset_cls=Asset)


@app.test_connectivity()
def test_connectivity(client: SOARClient, asset: Asset) -> None:
    client.debug(f"testing connectivity against {asset.base_url}")


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(action_type="test", verbose="Reverses a string.")
def reverse_string(
    param: ReverseStringParams, client: SOARClient
) -> ReverseStringOutput:
    client.debug("params", param.json())
    reversed_string = param.input_string[::-1]
    client.debug("reversed_string", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


if __name__ == "__main__":
    app.cli()
