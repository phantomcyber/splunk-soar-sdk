from typing import Annotated, Optional
import datetime
from pathlib import Path
import shutil
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from soar_sdk.code_renderers.app_renderer import AppContext, AppRenderer
from soar_sdk.code_renderers.toml_renderer import TomlContext, TomlRenderer
from soar_sdk.compat import PythonVersion
from soar_sdk.paths import APP_INIT_TEMPLATES

console = Console()  # For printing lots of pretty colors and stuff
WORK_DIR = Path.cwd()


init = typer.Typer(invoke_without_command=True)


@init.callback()
def init_sdk_app(
    name: Annotated[str, typer.Option(prompt="App name")],
    description: Annotated[str, typer.Option(prompt="App description")],
    authors: Annotated[list[str], typer.Option(default_factory=list)],
    python_versions: Annotated[
        list[PythonVersion],
        typer.Option(
            "--python-version",
            "-p",
            help="Supported Python versions for the app.",
            default_factory=lambda: [str(py) for py in PythonVersion.all()],
        ),
    ],
    dependencies: Annotated[list[str], typer.Option(default_factory=list)],
    appid: Annotated[uuid.UUID, typer.Option(default_factory=uuid.uuid4)],
    app_dir: Annotated[
        Path,
        typer.Option(
            file_okay=False,
            dir_okay=True,
            writable=True,
            readable=True,
            resolve_path=True,
            prompt="Directory in which to initialize the SDK app",
        ),
    ] = WORK_DIR,
    copyright: str = "Copyright (c) {year} Splunk Inc.",  # noqa: A002
    version: str = "1.0.0",
    # TODO: Enum for app types
    type: str = "generic",  # noqa: A002
    vendor: str = "Splunk Inc.",
    publisher: str = "Splunk Inc.",
    logo: Annotated[
        Optional[Path],
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    logo_dark: Annotated[
        Optional[Path],
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    product: Optional[str] = None,
    fips_compliant: bool = False,
    overwrite: bool = False,
) -> None:
    """
    Initialize a new SOAR app in the specified directory.
    """
    app_dir.mkdir(exist_ok=True)

    if next(app_dir.iterdir(), None) is not None:
        if overwrite:
            shutil.rmtree(app_dir)
            app_dir.mkdir()
        else:
            rprint(
                f"[red]Output directory {app_dir} is not empty. Use --overwrite to force conversion."
            )
            raise typer.Exit(code=1)

    console.print(Panel(f"Creating new app at {app_dir}", expand=False))
    console.rule()

    rprint("[blue]Creating app directory structure")
    src_dir = app_dir / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").touch()

    # Use Jinja2 to render the pyproject.toml file
    rprint("[blue]Creating pyproject.toml")
    toml_context = TomlContext(
        name=name,
        version=version,
        description=description,
        copyright=copyright.format(
            year=datetime.datetime.now(datetime.timezone.utc).year
        ),
        python_versions=python_versions,
        authors=authors,
        dependencies=dependencies,
    )
    toml_text = TomlRenderer(toml_context).render()
    (app_dir / "pyproject.toml").write_text(toml_text)

    # Copy app logos
    rprint("[blue]Copying app logos")
    if not logo:
        rprint("[dim]No logo provided. Using default")
        logo = APP_INIT_TEMPLATES / "basic_app/logo.svg"
    if not logo_dark:
        rprint("[dim]No dark logo provided. Using default")
        logo_dark = APP_INIT_TEMPLATES / "basic_app/logo_dark.svg"

    shutil.copy(logo, app_dir / logo.name)
    shutil.copy(logo_dark, app_dir / logo_dark.name)

    rprint("[blue]Creating app code")
    app_context = AppContext(
        name=name,
        app_type=type,
        logo=logo.name,
        logo_dark=logo_dark.name,
        product_vendor=vendor,
        product_name=product or name,
        publisher=publisher,
        appid=str(appid),
        fips_compliant=fips_compliant,
    )
    app_text = AppRenderer(app_context).render()
    (app_dir / "src/app.py").write_text(app_text)

    rprint(f"[green]Successfully created app at[/] {app_dir}")
