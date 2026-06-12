import uuid
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from soar_sdk.compat import PythonVersion

DEFAULT_COPYRIGHT = "Copyright (c) {year} Splunk Inc."
DEFAULT_VERSION = "1.0.0"
DEFAULT_TYPE = "generic"
DEFAULT_VENDOR = "Splunk Inc."
DEFAULT_PUBLISHER = "Splunk Inc."
DEFAULT_UV_INDEX = "https://pypi.python.org/simple"


@dataclass
class InitWizardConfig:
    """Configuration collected by the interactive init wizard."""

    name: str
    description: str
    app_dir: Path
    private: bool
    authors: list[str] = field(default_factory=list)
    python_versions: list[PythonVersion] = field(default_factory=PythonVersion.all)
    dependencies: list[str] = field(default_factory=list)
    appid: uuid.UUID = field(default_factory=uuid.uuid4)
    copyright: str = DEFAULT_COPYRIGHT
    version: str = DEFAULT_VERSION
    type: str = DEFAULT_TYPE
    vendor: str = DEFAULT_VENDOR
    publisher: str = DEFAULT_PUBLISHER
    uv_index: str = DEFAULT_UV_INDEX
    product: str | None = None
    fips_compliant: bool = False
    encrypt_cache_state: bool = True
    encrypt_ingest_state: bool = True
    overwrite: bool = False


def run_init_wizard(
    *, console: Console, default_app_dir: Path
) -> InitWizardConfig | None:
    """Collect init options interactively."""
    console.print(
        Panel(
            "[bold]Create a new Splunk SOAR app[/]\n"
            "Press Enter to accept defaults shown in brackets.",
            expand=False,
        )
    )

    name = _ask_required("App name", console=console)
    description = _ask_required("App description", console=console)
    app_dir = _ask_path(
        "App directory", default=_get_default_app_dir(default_app_dir, name)
    )
    publish_to_splunkbase = Confirm.ask(
        "Will you publish this app to Splunkbase?", default=True
    )

    config = InitWizardConfig(
        name=name,
        description=description,
        app_dir=app_dir,
        private=not publish_to_splunkbase,
    )

    if Confirm.ask("Configure advanced settings?", default=False):
        config.authors = _ask_csv("Authors")
        config.python_versions = _ask_python_versions(console)
        config.dependencies = _ask_csv("Dependencies")
        config.version = _ask_required(
            "App version", default=DEFAULT_VERSION, console=console
        )
        config.type = _ask_required("App type", default=DEFAULT_TYPE, console=console)
        config.vendor = _ask_required(
            "Product vendor", default=DEFAULT_VENDOR, console=console
        )
        config.publisher = _ask_required(
            "Publisher", default=DEFAULT_PUBLISHER, console=console
        )
        config.product = Prompt.ask("Product name", default=name).strip() or None
        config.fips_compliant = Confirm.ask("FIPS compliant?", default=False)
        config.encrypt_cache_state = Confirm.ask("Encrypt cache state?", default=True)
        config.encrypt_ingest_state = Confirm.ask("Encrypt ingest state?", default=True)
        config.uv_index = _ask_required(
            "Python package index", default=DEFAULT_UV_INDEX, console=console
        )
        config.overwrite = Confirm.ask(
            "Overwrite the app directory if it is not empty?", default=False
        )

    _print_summary(config, console)
    if not Confirm.ask("Create app?", default=True):
        console.print("[yellow]App creation cancelled.[/]")
        return None

    return config


def _ask_required(label: str, *, console: Console, default: str | None = None) -> str:
    while True:
        if default is None:
            value = Prompt.ask(label).strip()
        else:
            value = Prompt.ask(label, default=default).strip()
        if value:
            return value
        console.print(f"[red]{label} is required.[/]")


def _ask_path(label: str, *, default: Path) -> Path:
    value = Prompt.ask(label, default=str(default)).strip()
    return Path(value).expanduser().resolve()


def _get_default_app_dir(base_dir: Path, app_name: str) -> Path:
    return base_dir / app_name


def _ask_csv(label: str) -> list[str]:
    value = Prompt.ask(f"{label} (comma-separated)", default="").strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _ask_python_versions(console: Console) -> list[PythonVersion]:
    while True:
        value = Prompt.ask(
            "Supported Python versions",
            default=PythonVersion.all_csv(),
        ).strip()
        try:
            return PythonVersion.from_csv(value)
        except ValueError as exception:
            console.print(f"[red]{exception}[/]")


def _print_summary(config: InitWizardConfig, console: Console) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Name", config.name)
    table.add_row("Description", config.description)
    table.add_row("Directory", str(config.app_dir))
    table.add_row("Publish to Splunkbase", "no" if config.private else "yes")
    table.add_row("Version", config.version)
    table.add_row(
        "Python versions",
        ", ".join(str(version) for version in config.python_versions),
    )
    if config.authors:
        table.add_row("Authors", ", ".join(config.authors))
    if config.dependencies:
        table.add_row("Dependencies", ", ".join(config.dependencies))
    table.add_row("Product", config.product or config.name)
    table.add_row("Vendor", config.vendor)
    table.add_row("Publisher", config.publisher)
    table.add_row("FIPS compliant", "yes" if config.fips_compliant else "no")
    table.add_row("Encrypt cache state", "yes" if config.encrypt_cache_state else "no")
    table.add_row(
        "Encrypt ingest state", "yes" if config.encrypt_ingest_state else "no"
    )
    table.add_row("Package index", config.uv_index)
    table.add_row("Overwrite", "yes" if config.overwrite else "no")

    console.print(Panel(table, title="App settings", expand=False))
