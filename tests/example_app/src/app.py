from typing import Union
from collections.abc import Iterator
from datetime import datetime, timezone
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import OnPollParams
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.logging import getLogger

logger = getLogger()


class Asset(BaseAsset):
    base_url: str = AssetField(default="https://example")
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
    soar.get("rest/version")
    logger.info(f"testing connectivity against {asset.base_url}")
    logger.debug("hello")
    logger.warning("this is a warning")
    logger.progress("this is a progress message")


from .actions.reverse_string import render_reverse_string_view, reverse_string

app.register_action(
    reverse_string,
    action_type="investigate",
    verbose="Reverses a string.",
    view_template="reverse_string.html",
    view_handler=render_reverse_string_view,
)

from .actions.generate_category import render_statistics_chart, generate_statistics

app.register_action(
    generate_statistics,
    action_type="investigate",
    verbose="Generate statistics with pie chart reusable component.",
    view_handler=render_statistics_chart,
)


@app.on_poll()
def on_poll(
    params: OnPollParams, client: SOARClient, asset: Asset
) -> Iterator[Union[Container, Artifact]]:
    # Create container first for artifacts
    yield Container(
        name="Network Alerts",
        description="Some network-related alerts",
        severity="medium",
    )

    # Simulate collecting 2 network artifacts that will be put in the network alerts container
    for i in range(1, 3):
        logger.info(f"Processing network artifact {i}")

        alert_id = f"testalert-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{i}"
        artifact = Artifact(
            name=f"Network Alert {i}",
            label="alert",
            severity="medium",
            source_data_identifier=alert_id,
            type="network",
            description=f"Example network alert {i} from polling operation",
            data={
                "alert_id": alert_id,
                "source_ip": f"10.0.0.{i}",
                "destination_ip": "192.168.0.1",
                "protocol": "TCP",
            },
        )

        yield artifact


from .actions.async_action import async_process, sync_process

app.register_action(
    async_process,
    action_type="investigate",
    verbose="Processes a message asynchronously with concurrent HTTP requests.",
)

app.register_action(
    sync_process,
    action_type="investigate",
    verbose="Processes a message synchronously with sequential HTTP requests.",
)


if __name__ == "__main__":
    app.cli()
