from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, MakeRequestOutput, OutputField
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset, FieldCategory
from soar_sdk.logging import getLogger
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.models.finding import Finding
from soar_sdk.params import (
    MakeRequestParams,
    OnESPollParams,
    OnPollParams,
    Param,
    Params,
)

logger = getLogger()

# Test mail template for ES findings
SAMPLE_EMAIL_TEMPLATE = """From: suspicious@example.com
To: {user}
Subject: Suspicious Activity Detected
Date: {date}

This is a suspicious email that triggered the risk threshold.
Event ID: {event_id}
"""

# Test event data CSV for attachments
SAMPLE_EVENTS_CSV = """timestamp,user,action,risk_score
{timestamp},{{user}},login_failed,{{risk_score}}
{timestamp},{{user}},access_denied,{{secondary_score}}
"""


class Asset(BaseAsset):
    base_url: str = AssetField(default="https://example")
    api_key: str = AssetField(sensitive=True, description="API key for authentication")
    key_header: str = AssetField(
        default="Authorization",
        value_list=["Authorization", "X-API-Key"],
        description="Header for API key authentication",
    )
    timezone: ZoneInfo
    timezone_with_default: ZoneInfo = AssetField(
        default=ZoneInfo("America/Denver"), category=FieldCategory.ACTION
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
    container_id = soar.get_executing_container_id()
    logger.info(f"current executing container's container_id is: {container_id}")
    asset_id = soar.get_asset_id()
    logger.info(f"current executing container's asset_id is: {asset_id}")
    logger.info(f"testing connectivity against {asset.base_url}")
    logger.debug("hello")
    logger.warning("this is a warning")
    logger.progress("this is a progress message")


class ActionOutputSummary(ActionOutput):
    is_success: bool


@app.action()
def test_summary_with_list_output(
    params: Params, asset: Asset, soar: SOARClient
) -> list[ActionOutput]:
    soar.set_summary(ActionOutputSummary(is_success=True))
    return [ActionOutput(), ActionOutput()]


@app.action()
def test_empty_list_output(
    params: Params, asset: Asset, soar: SOARClient
) -> list[ActionOutput]:
    return []


class JsonOutput(ActionOutput):
    name: str = OutputField(example_values=["John", "Jane", "Jim"], column_name="Name")
    age: int = OutputField(example_values=[25, 30, 35], column_name="Age")


class TableParams(Params):
    company_name: str = Param(column_name="Company Name", default="Splunk")


@app.action(render_as="json")
def test_json_output(params: Params, asset: Asset, soar: SOARClient) -> JsonOutput:
    return JsonOutput(name="John", age=25)


@app.action(render_as="table")
def test_table_output(
    params: TableParams, asset: Asset, soar: SOARClient
) -> JsonOutput:
    return JsonOutput(name="John", age=25)


from .actions.reverse_string import render_reverse_string_view

app.register_action(
    "actions.reverse_string:reverse_string",
    action_type="investigate",
    verbose="Reverses a string.",
    view_template="reverse_string.html",
    view_handler=render_reverse_string_view,
)

from .actions.generate_category import render_statistics_chart

app.register_action(
    "actions.generate_category:generate_statistics",
    action_type="investigate",
    verbose="Generate statistics with pie chart reusable component.",
    view_handler=render_statistics_chart,
)


class MakeRequestParamsCustom(MakeRequestParams):
    endpoint: str = Param(
        description="The endpoint to send the request to. Base url is already included in the endpoint.",
        required=True,
    )


@app.make_request()
def http_action(params: MakeRequestParamsCustom, asset: Asset) -> MakeRequestOutput:
    logger.info(f"HTTP action triggered with params: {params}")
    return MakeRequestOutput(
        status_code=200,
        response_body=f"Base url is {asset.base_url}",
    )


@app.on_poll()
def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Container | Artifact]:
    if params.is_manual_poll():
        logger.info("Manual poll (poll now) detected")
    else:
        logger.info("Scheduled poll detected")

    # Create container first for artifacts
    yield Container(
        name="Network Alerts",
        description="Some network-related alerts",
        severity="medium",
    )

    # Simulate collecting 2 network artifacts that will be put in the network alerts container
    for i in range(1, 3):
        logger.info(f"Processing network artifact {i}")

        alert_id = f"testalert-{datetime.now(UTC).strftime('%Y%m%d')}-{i}"
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


@app.on_es_poll()
def on_es_poll(
    params: OnESPollParams, soar: SOARClient, asset: Asset
) -> Generator[Finding, int | None]:
    for i in range(1, 3):
        logger.info(f"Processing ES finding {i}")

        container_id = yield Finding(
            rule_title=f"Risk threshold exceeded for user-{i}",
            rule_description="Risk Threshold Exceeded for an object over a 24 hour period",
            security_domain="threat",
            risk_object=f"user{i}@example.com",
            risk_object_type="user",
            risk_score=75.0 + (i * 10),
            status="New",
            urgency="medium",
        )

        # Attach evidence
        email_evidence = SAMPLE_EMAIL_TEMPLATE.format(
            user=f"user{i}@example.com",
            date=datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            event_id=f"EVT-{i:04d}",
        )

        event_data = SAMPLE_EVENTS_CSV.format(
            timestamp=datetime.now(UTC).isoformat()
        ).format(
            user=f"user{i}@example.com",
            risk_score=75.0 + (i * 10),
            secondary_score=50.0 + (i * 5),
        )

        soar.vault.create_attachment(
            container_id,
            file_content=email_evidence,
            file_name=f"suspicious_email_user{i}.eml",
            metadata={"type": "email_evidence", "source": "investigation_mailbox"},
        )
        soar.vault.create_attachment(
            container_id,
            file_content=event_data,
            file_name=f"risk_events_user{i}.csv",
            metadata={"type": "event_log", "event_count": "2"},
        )


app.register_action(
    "actions.async_action:async_process",
    action_type="investigate",
    verbose="Processes a message asynchronously with concurrent HTTP requests.",
)

app.register_action(
    "actions.async_action:sync_process",
    action_type="investigate",
    verbose="Processes a message synchronously with sequential HTTP requests.",
)


class GeneratorActionOutput(ActionOutput):
    iteration: int


class GeneratorActionSummary(ActionOutput):
    total_iterations: int


@app.action(summary_type=GeneratorActionSummary)
def generator_action(
    params: Params, soar: SOARClient[GeneratorActionSummary], asset: Asset
) -> Iterator[GeneratorActionOutput]:
    """Generates a sequence of numbers."""
    logger.info(f"Generator action triggered with params: {params}")
    for i in range(5):
        yield GeneratorActionOutput(iteration=i)
    soar.set_summary(GeneratorActionSummary(total_iterations=5))


@app.action()
def write_state(params: Params, soar: SOARClient, asset: Asset) -> ActionOutput:
    asset.cache_state.clear()
    assert asset.cache_state == {}
    asset.cache_state["value"] = "banana"
    return ActionOutput()


@app.action()
def read_state(params: Params, soar: SOARClient, asset: Asset) -> ActionOutput:
    assert asset.cache_state == {"value": "banana"}
    return ActionOutput()


if __name__ == "__main__":
    app.cli()
