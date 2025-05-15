#!/usr/bin/env python
from typing import Iterator, Dict, Any, List
from datetime import datetime, timedelta
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import Params, OnPollParams
from soar_sdk.action_results import ActionOutput
from soar_sdk.logging import getLogger

logger = getLogger()


class Asset(BaseAsset):
    base_url: str
    api_key: str = AssetField(sensitive=True, description="API key for authentication")
    key_header: str = AssetField(
        default="Authorization",
        value_list=["Authorization", "X-API-Key"],
        description="Header for API key authentication",
    )


app = App(
    asset_cls=Asset,
    name="example_app",
    appid="9b388c08-67de-4ca4-817f-26f8fb7cbf55",
    app_type="sandbox",
    product_vendor="Splunk Inc.",
    logo="logo.svg",
    logo_dark="logo_dark.svg",
    product_name="Example App",
    publisher="Splunk Inc.",
    min_phantom_version="6.2.2.134",
)


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    logger.info(f"testing connectivity against {asset.base_url}")


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(action_type="test", verbose="Reverses a string.")
def reverse_string(param: ReverseStringParams, soar: SOARClient) -> ReverseStringOutput:
    logger.debug("params: %s", param)
    reversed_string = param.input_string[::-1]
    client.debug("reversed_string", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


@app.on_poll()
def on_poll(params: OnPollParams, client: SOARClient, asset: Asset) -> Iterator[Dict[str, Any]]:
    """
    Example on_poll implementation using a generator function with yield.
    
    This function demonstrates polling for data from a hypothetical API and yielding
    artifacts that will be automatically saved by the SDK.
    """
    client.save_progress("Starting poll operation")
    
    # Log the polling parameters
    client.debug("Polling from", f"Start time: {params.start_time}, End time: {params.end_time}")
    client.debug("Container count", str(params.container_count))
    client.debug("Artifact count", str(params.artifact_count))
    client.debug("Container ID", str(params.container_id))
    
    # Example of using asset configuration
    client.debug("Using base URL", asset.base_url)
    
    # In a real app, you would fetch data from an external API here
    # For this example, we'll create some sample artifacts
    
    # Example of respecting the artifact count limit
    artifacts_to_create = min(5, params.artifact_count)
    
    # Simulate collecting artifacts - using generator approach with yield
    for i in range(artifacts_to_create):
        client.save_progress(f"Processing artifact {i+1}/{artifacts_to_create}")
        
        # Create a sample artifact
        artifact = {
            "name": f"Sample Alert {i+1}",
            "label": "alert",
            "severity": "medium",
            "source": asset.base_url,
            "type": "network",
            "description": f"Example alert {i+1} from polling operation",
            "data": {
                "alert_id": f"ALERT-{datetime.now().strftime('%Y%m%d')}-{i+1}",
                "detected_time": (datetime.now() - timedelta(hours=i)).isoformat(),
                "source_ip": f"10.0.0.{i+1}",
                "destination_ip": "192.168.1.100",
                "protocol": "TCP"
            }
        }
        
        # Yield the artifact
        client.save_progress(f"Found artifact: {artifact['name']}")
        yield artifact


if __name__ == "__main__":
    app.cli()
