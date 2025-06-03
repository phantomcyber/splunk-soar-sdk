import contextlib
from datetime import timedelta
import humanize
import typer

import tarfile
from io import BytesIO
import json
from pathlib import Path
import asyncio
import time
from typing import Optional, Annotated
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel

from soar_sdk.cli.manifests.processors import ManifestProcessor
from soar_sdk.meta.dependencies import DependencyWheel
from soar_sdk.cli.path_utils import context_directory
from soar_sdk.cli.package.utils import phantom_get_login_session, phantom_install_app
from itertools import chain
import os
import httpx

package = typer.Typer(invoke_without_command=True)
console = Console()  # For printing lots of pretty colors and stuff


async def collect_all_wheels(wheels: set[DependencyWheel]) -> list[tuple[str, bytes]]:
    """
    Asynchronously collect all wheels from the given set of DependencyWheel objects.
    """
    # Create progress bar for tracking wheel collection
    progress = tqdm(
        total=len(wheels),
        desc="Downloading wheels",
        unit="wheel",
        colour="green",
        ncols=80,
    )

    async def collect_from_wheel(wheel: DependencyWheel) -> list[tuple[str, bytes]]:
        result = []
        # This actually is covered, but pytest-cov branch coverage
        # has a bug with the end of async for loops
        async for path, data in wheel.collect_wheels():  # pragma: no cover
            result.append((path, data))
        # Update progress bar after each wheel is processed
        progress.update(1)
        return result

    # Use asyncio.gather to truly run all wheel collections concurrently
    with contextlib.closing(progress):
        wheel_data_lists = await asyncio.gather(
            *(collect_from_wheel(wheel) for wheel in wheels)
        )

    # Use itertools.chain to flatten the list of lists
    return list(chain.from_iterable(wheel_data_lists))


@package.command()
def build(
    project_context: Annotated[
        Path,
        typer.Argument(
            default_factory=Path.cwd, show_default="current working directory"
        ),
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Option("--output-file", "-o", show_default="derived from pyproject.toml"),
    ] = None,
    with_sdk_wheel_from: Annotated[
        Optional[Path],
        typer.Option(
            "--with-sdk-wheel-from",
            "-w",
            help="Optional path to an SDK wheel to include",
        ),
    ] = None,
) -> None:
    """
    Build a SOAR app package.

    Args:
        project_context: Path to the app project directory
    Options:
        --output-file, -o: Path where the packaged app will be saved
    """
    # Start timing the build process
    start_time = time.time()
    project_context = project_context.resolve()
    if with_sdk_wheel_from:
        with_sdk_wheel_from = with_sdk_wheel_from.resolve()

    console.print(Panel("[bold]Building SOAR App Package[/]", expand=False))
    console.print(f"[blue]App directory:[/] {project_context}")

    # Resolve the output path relative to the user's working directory, not the project context
    cwd = Path.cwd()
    if output_file is not None:
        output_file = output_file.resolve()
        console.print(f"[blue]Output file:[/] {output_file}")

    with context_directory(project_context):
        app_meta = ManifestProcessor("manifest.json", ".").build()
        app_name = app_meta.name

        if output_file is None:
            output_file = cwd / f"{app_name}.tgz"
            console.print(f"[blue]Output file:[/] {output_file}")

        console.print(f"Generated manifest for app:[green] {app_name}[/]")

        def filter_source_files(t: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
            if t.isdir() and "__pycache__" not in t.name:
                return t
            if t.isfile() and t.name.endswith(".py"):
                return t
            return None

        with tarfile.open(output_file, "w:gz") as app_tarball:
            # Collect all wheels from both Python versions
            all_wheels = set(
                app_meta.pip39_dependencies.wheel + app_meta.pip313_dependencies.wheel
            )

            # Run the async collection function within an event loop
            console.print(
                f"[yellow]Collecting [bold]{len(all_wheels)}[/bold] wheel{'' if len(all_wheels) == 1 else 's'} for package[/]"
            )
            wheel_data = asyncio.run(collect_all_wheels(all_wheels))

            # Add all collected wheel data to the tarball
            for path, data in tqdm(
                wheel_data,
                colour="blue",
                ncols=80,
                desc="Adding wheels to package",
                unit="file",
            ):
                info = tarfile.TarInfo(f"{app_name}/{path}")
                info.size = len(data)
                app_tarball.addfile(info, BytesIO(data))

            console.print("Adding app files to package")
            app_tarball.add(app_meta.logo, f"{app_name}/{app_meta.logo}")
            app_tarball.add(app_meta.logo_dark, f"{app_name}/{app_meta.logo_dark}")
            app_tarball.add(
                "src", f"{app_name}/src", recursive=True, filter=filter_source_files
            )

            if with_sdk_wheel_from:
                console.print(f"[dim]Adding SDK wheel from {with_sdk_wheel_from}[/]")
                wheel_name = with_sdk_wheel_from.name

                wheel_archive_path = f"wheels/shared/{wheel_name}"
                app_tarball.add(with_sdk_wheel_from, f"{app_name}/{wheel_archive_path}")

                wheel_entry = DependencyWheel(
                    module="soar_sdk",
                    input_file=wheel_archive_path,
                    input_file_aarch64=wheel_archive_path,
                )
                app_meta.pip39_dependencies.wheel.append(wheel_entry)
                app_meta.pip313_dependencies.wheel.append(wheel_entry)

            console.print("Writing manifest")
            manifest_json = json.dumps(app_meta.to_json_manifest(), indent=4).encode()
            manifest_info = tarfile.TarInfo(f"{app_name}/manifest.json")
            manifest_info.size = len(manifest_json)
            app_tarball.addfile(manifest_info, BytesIO(manifest_json))

    # Calculate elapsed time
    elapsed = humanize.precisedelta(timedelta(seconds=time.time() - start_time))

    console.print(f"[green]✓ App name:[/] {app_name}")
    console.print(f"[green]✓ Package successfully built and saved to:[/] {output_file}")
    console.print(f"[blue]⏱ Total build time:[/] {elapsed}")


async def upload_app(
    soar_instance: str, username: str, password: str, app_tarball: Path
) -> httpx.Response:
    """
    Asynchronously install the app on a SOAR instance
    """
    base_url = (
        soar_instance
        if soar_instance.startswith("https://")
        else f"https://{soar_instance}"
    )

    payload = {"app": app_tarball.read_bytes()}
    async with phantom_get_login_session(base_url, username, password) as client:
        response = await phantom_install_app(client, "app_install", payload)
    return response


@package.command()
def install(app_tarball: Path, soar_instance: str, username: str = "") -> None:
    """
    Install the app tarball to the specified SOAR instance. Note to authenticate with your SOAR instance you can either set the PHANTOM_PASSWORD environment variable or enter the password when prompted.
    """
    app_tarball = app_tarball.resolve()
    if not app_tarball.exists():
        raise typer.BadParameter(f"App tarball {app_tarball} does not exist")

    if not app_tarball.is_file():
        raise typer.BadParameter(f"{app_tarball} is not a file")

    if not username:
        username = typer.prompt("Please enter your SOAR username")

    if not (password := os.getenv("PHANTOM_PASSWORD", "")):
        password = typer.prompt("Please enter your SOAR password", hide_input=True)

    app_install_request = asyncio.run(
        upload_app(soar_instance, username, password, app_tarball)
    )

    try:
        app_install_request.raise_for_status()
    except Exception as exception:
        console.print(f"[bold red]Error:[/] {exception}", style="red")
        raise typer.Exit(1) from exception

    console.print(f"App installed successfully on {soar_instance}")
