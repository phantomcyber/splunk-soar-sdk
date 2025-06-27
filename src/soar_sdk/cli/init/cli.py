from typing import Annotated, Optional
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from soar_sdk.cli.manifests.deserializers import AppMetaDeserializer
from soar_sdk.code_renderers.action_renderer import ActionRenderer
from soar_sdk.code_renderers.app_renderer import AppContext, AppRenderer
from soar_sdk.code_renderers.asset_renderer import AssetContext, AssetRenderer
from soar_sdk.code_renderers.toml_renderer import TomlContext, TomlRenderer
from soar_sdk.compat import PythonVersion
from soar_sdk.meta.app import AppMeta
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


convert = typer.Typer(invoke_without_command=True)


@convert.callback()
def convert_connector_to_sdk(
    app_dir: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            writable=True,
            readable=True,
            resolve_path=True,
        ),
    ],
    output_dir: Annotated[
        Optional[Path],
        typer.Argument(
            file_okay=False,
            dir_okay=True,
            writable=True,
            readable=True,
            resolve_path=True,
            help="Directory to output the converted SDK app.",
        ),
    ] = None,
    overwrite: bool = False,
) -> None:
    """
    Convert a SOAR connector to a SOAR SDK app.

    This command will convert a SOAR connector directory into a SOAR SDK app directory.
    The connector directory should contain the necessary files and structure for conversion.
    """
    if output_dir is None:
        output_dir = app_dir / "sdk_app"

    console.line()
    console.print(Panel(f"Converting connector at {app_dir}", expand=False))

    json_path = get_app_json(app_dir)

    app_meta = AppMetaDeserializer.from_app_json(json_path)

    # Convert the main module path to the SDK format, but save a reference to the original
    app_meta.main_module = "src.app:app"

    init_sdk_app(
        name=app_meta.project_name,
        description=app_meta.description,
        authors=[author.name for author in app_meta.contributors],
        python_versions=app_meta.python_version,
        dependencies=[],
        app_dir=output_dir,
        copyright=app_meta.license,
        version=app_meta.app_version,
        appid=uuid.UUID(app_meta.appid),
        type=app_meta.type,
        vendor=app_meta.product_vendor,
        product=app_meta.product_name,
        publisher=app_meta.publisher,
        logo=app_dir / app_meta.logo,
        logo_dark=app_dir / app_meta.logo_dark,
        fips_compliant=app_meta.fips_compliant,
        overwrite=overwrite,
    )

    with console.status("[green]Adding dependencies to app."):
        resolve_dependencies(app_dir, output_dir)

    with console.status("[green]Adding asset definition to app."):
        generate_asset_definition(app_meta, output_dir / "src/app.py")

    with console.status("[green]Adding action definitions to app."):
        generate_action_definitions(app_meta, output_dir / "src/app.py")

    with console.status("[green]Adding action view handlers to app."):
        # This is a placeholder for any future action view handler generation
        pass

    with console.status("[green]Adding webhook handlers to app."):
        # This is a placeholder for any future webhook handler generation
        pass

    subprocess.run(["ruff", "format", output_dir], check=True)  # noqa: S603, S607

    console.print(
        Panel(
            f"[green]Successfully converted app [/]{app_dir}[green] -> [/]{output_dir}",
            expand=False,
        )
    )


def resolve_dependencies(app_dir: Path, output_dir: Path) -> None:
    """
    Write the app metadata to a pyproject.toml file in the output directory.
    """
    validated_deps = {"splunk-soar-sdk"}

    if (req_txt := app_dir / "requirements.txt").exists():
        deps = req_txt.read_text().splitlines()

        # Be extra careful to avoid untrusted inputs
        for _dep in deps:
            dep = _dep.strip()
            if not dep or dep.startswith("#"):
                continue
            if not re.match(r"^[a-zA-Z0-9_.=<>~-]+$", dep):
                rprint(f"[yellow]Skipping invalid dependency: {dep}[/]")
                continue
            validated_deps.add(dep)

    subprocess.run(  # noqa: S603 [inputs validated above]
        ["uv", "add", *validated_deps],  # noqa: S607
        env={"PATH": os.environ["PATH"]},
        cwd=output_dir,
        check=True,
        capture_output=True,
    )


def get_app_json(app_dir: Path) -> Path:
    """
    Find the app's JSON metadata file in the given directory

    Args:
        app_dir (Path): The directory to search for app.json.

    Returns:
        app_json (Path): The path to the app's JSON metadata file.
    """
    for path in app_dir.glob("*.json"):
        # Some connectors have postman JSONs. Skip those quickly
        if ".postman_collection." in path.name:
            continue

        # Only way to find an app's JSON is to crack it open and check the contents
        try:
            manifest = json.loads(path.read_text())
            if not (isinstance(manifest, dict) and "main_module" in manifest):
                raise ValueError()

            return path
        except Exception as e:
            console.print(e)
            print(f"[dim]Skipping {path} as it is not a valid app manifest.[/]")

    raise FileNotFoundError(
        f"No valid app manifest found in {app_dir}. Please ensure the directory contains a valid app JSON file."
    )


def generate_asset_definition(
    app_meta: AppMeta,
    app_py_path: Path,
) -> None:
    """
    Generate the asset definition from the app metadata and save it to the specified output path.
    """
    asset_context: list[AssetContext] = []
    for name, config_spec in app_meta.configuration.items():
        if config_spec["data_type"].startswith("ph"):
            # Skip the cosmetic placeholder fields
            continue

        asset_context.append(
            AssetContext(
                name=name,
                description=config_spec.get("description"),
                required=config_spec.get("required", False),
                default=config_spec.get("default"),
                data_type=config_spec["data_type"],
                value_list=config_spec.get("value_list"),
            )
        )

    renderer = AssetRenderer(asset_context)
    asset_def = renderer.render()
    app_content = app_py_path.read_text()
    app_content = re.sub(
        r"class Asset\(BaseAsset\):\n +pass",
        f"{asset_def}",
        app_content,
        count=1,
        flags=re.MULTILINE,
    )
    app_py_path.write_text(app_content)


def generate_action_definitions(
    app_meta: AppMeta,
    app_py_path: Path,
) -> None:
    """
    Generate action definitions from the app metadata and save them to the specified output path.
    """
    action_defs: list[str] = []

    for action_meta in app_meta.actions:
        renderer = ActionRenderer(action_meta)

        # Push reserved actions to the front of the list
        if action_meta.action in ActionRenderer.STUBS:
            action_defs.insert(0, renderer.render())
        else:
            action_defs.append(renderer.render())

    action_str = "\n\n".join(action_defs)
    app_content = app_py_path.read_text()
    app_content = re.sub(
        r"(^if __name__ == .+)",
        f"{action_str}\n\n\\1",
        app_content,
        count=1,
        flags=re.MULTILINE,
    )
    app_py_path.write_text(app_content)
