import json
from pprint import pprint

import typer

from .processors import MetafileUpdateProcessor

metafiles = typer.Typer()


@metafiles.command()
def display(filename):
    with open(filename, "r") as f:
        meta = json.load(f)

    pprint(meta)


@metafiles.command()
def create(filename, project_context: str):
    MetafileUpdateProcessor(filename, project_context).create()
