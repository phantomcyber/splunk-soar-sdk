import json
from pathlib import Path
from pprint import pprint
from typing import Annotated

import typer

from .notice import NoticeGenerator
from .processors import ManifestProcessor

manifests = typer.Typer()


@manifests.command()
def display(filename: str) -> None:
    """Parse and print the contents of a manifest JSON file."""
    with open(filename) as f:
        meta = json.load(f)

    pprint(meta)


@manifests.command()
def create(filename: str, project_context: str) -> None:
    """Create a manifest file from the given project context."""
    ManifestProcessor(filename, project_context).create()


@manifests.command()
def create_notice(
    project_context: Annotated[
        Path,
        typer.Argument(
            default_factory=Path.cwd,
            show_default="current directory",
            help="Path to the SOAR app project directory.",
        ),
    ],
    output_file: Annotated[
        Path | None,
        typer.Option(
            "--output-file",
            "-o",
            show_default="<project_context>/NOTICE",
            help="Output path for the NOTICE file.",
        ),
    ] = None,
) -> None:
    """Generate a NOTICE file with third-party license attributions."""
    effective_output = (
        output_file if output_file is not None else project_context / "NOTICE"
    )
    NoticeGenerator(project_context).generate(effective_output)
