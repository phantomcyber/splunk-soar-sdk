import json
from pprint import pprint

import typer

from .processors import ManifestProcessor

manifests = typer.Typer()


@manifests.command()
def display(filename):
    with open(filename, "r") as f:
        meta = json.load(f)

    pprint(meta)


@manifests.command()
def create(filename, project_context: str):
    ManifestProcessor(filename, project_context).create()
