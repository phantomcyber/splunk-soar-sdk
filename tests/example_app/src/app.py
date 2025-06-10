#!/usr/bin/env python
from typing import Union
from collections.abc import Iterator
from datetime import datetime, timezone
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import Params, OnPollParams
from soar_sdk.action_results import ActionOutput
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.views.components.pie_chart import PieChartData
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
    logger.debug("reversed_string %s", reversed_string)
    return ReverseStringOutput(reversed_string=reversed_string)


class ReverseStringViewOutput(ActionOutput):
    original_string: str
    reversed_string: str


@app.view_handler(template="reverse_string.html")
def render_reverse_string_view(output: list[ReverseStringViewOutput]) -> dict:
    return {
        "original": output[0].original_string,
        "reversed": output[0].reversed_string,
    }


@app.action(
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


class StatisticsParams(Params):
    category: str


class StatisticsOutput(ActionOutput):
    category: str
    labels: list[str]
    values: list[int]


@app.view_handler()
def render_statistics_chart(output: list[StatisticsOutput]) -> PieChartData:
    stats = output[0]
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0", "#607D8B"]

    return PieChartData(
        title=f"{stats.category} Distribution",
        labels=stats.labels,
        values=stats.values,
        colors=colors,
    )


@app.action(
    action_type="investigate",
    verbose="Generate statistics with pie chart reusable component.",
    view_handler=render_statistics_chart,
)
def generate_statistics(param: StatisticsParams, soar: SOARClient) -> StatisticsOutput:
    if param.category.lower() == "test":
        breakdown = {
            "Malware": 45,
            "Phishing": 32,
            "Ransomware": 18,
            "Data Breach": 12,
            "DDoS": 8,
        }
    else:
        breakdown = {
            "Category A": 25,
            "Category B": 35,
            "Category C": 20,
            "Category D": 15,
            "Category E": 5,
        }

    return StatisticsOutput(
        category=param.category,
        labels=list(breakdown.keys()),
        values=list(breakdown.values()),
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


if __name__ == "__main__":
    app.cli()
