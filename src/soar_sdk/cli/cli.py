import typer

from soar_sdk import __version__
from soar_sdk.paths import SDK_ROOT
from soar_sdk.cli.manifests.cli import manifests
from soar_sdk.cli.package.cli import package
from soar_sdk.cli.init.cli import init, convert

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
HELP = """A command-line tool for helping with SOAR Apps development"""
app = typer.Typer(
    rich_markup_mode="rich",
    help=HELP,
    context_settings=CONTEXT_SETTINGS,
)

app.add_typer(manifests, name="manifests")
app.add_typer(package, name="package")
app.add_typer(init, name="init")
app.add_typer(convert, name="convert")


@app.command("version")
def version() -> None:
    """Display the version of the SOAR SDK."""
    typer.echo(f"Splunk SOAR SDK version: {__version__}")
    typer.echo(f"Installed in: {SDK_ROOT}")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
