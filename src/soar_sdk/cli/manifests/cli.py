import json
from pprint import pprint

import typer

from .processors import ManifestProcessor

manifests = typer.Typer()


@manifests.command()
def display(filename: str) -> None:
    with open(filename) as f:
        meta = json.load(f)

    pprint(meta)


@manifests.command()
def create(filename: str, project_context: str) -> None:
    ManifestProcessor(filename, project_context).create()
