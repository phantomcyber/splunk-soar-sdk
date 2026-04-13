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
from soar_sdk.models.finding import Finding, FindingAttachment, FindingEmail
from soar_sdk.params import (
    MakeRequestParams,
    OnESPollParams,
    OnPollParams,
    Param,
    Params,
)

logger = getLogger()

SAMPLE_EMAILS = [
    {
        "from": "phishing@malicious-domain.example.com",
        "to": "employee1@company.example.com",
        "subject": "Urgent: Verify your account",
        "date": None,
        "body": (
            "Dear user,\n\n"
            "Your account has been compromised. Please click the link below "
            "to verify your identity immediately.\n\n"
            "https://malicious-login.example.com/verify?token=abc123\n\n"
            "Regards,\nIT Support"
        ),
        "urls": [
            "https://malicious-login.example.com/verify?token=abc123",
        ],
        "attachment_name": "invoice.pdf",
        "attachment_data": b"fake pdf attachment content",
    },
    {
        "from": "spam@spoofed-bank.example.com",
        "to": "employee2@company.example.com",
        "subject": "Your payment is overdue",
        "date": None,
        "body": (
            "Hello,\n\n"
            "We noticed an outstanding balance on your account. "
            "Please review the attached statement and submit payment.\n\n"
            "https://fake-payment.example.com/pay\n\n"
            "Thank you,\nBilling Department"
        ),
        "urls": [
            "https://fake-payment.example.com/pay",
        ],
        "attachment_name": "statement.xlsx",
        "attachment_data": b"fake spreadsheet content",
    },
]


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


app.register_action(
    "actions.permissive_action:permissive_reverse_string",
    action_type="investigate",
    verbose="Reverses a string but doesn't care if it gets all its output fields.",
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
    for i, email_data in enumerate(SAMPLE_EMAILS, start=1):
        logger.info(f"Processing test finding {i}")

        date_str = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
        raw_eml = (
            f"From: {email_data['from']}\r\n"
            f"To: {email_data['to']}\r\n"
            f"Subject: {email_data['subject']}\r\n"
            f"Date: {date_str}\r\n"
            f"MIME-Version: 1.0\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n"
            f"{email_data['body']}"
        )

        yield Finding(
            rule_title=f"Test Finding {i}: {email_data['subject']}",
            email=FindingEmail(
                headers={
                    "From": email_data["from"],
                    "To": email_data["to"],
                    "Subject": email_data["subject"],
                    "Date": date_str,
                    "Content-Type": "text/plain; charset=utf-8",
                },
                body=email_data["body"],
                urls=email_data["urls"],
            ),
            attachments=[
                FindingAttachment(
                    file_name=f"email_{i}.eml",
                    data=raw_eml.encode("utf-8"),
                    is_raw_email=True,
                ),
                FindingAttachment(
                    file_name=email_data["attachment_name"],
                    data=email_data["attachment_data"],
                    is_raw_email=False,
                ),
            ],
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
