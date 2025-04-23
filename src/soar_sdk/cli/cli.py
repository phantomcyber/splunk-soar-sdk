import typer

from soar_sdk.cli.manifests.cli import manifests

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
HELP = """A command-line tool for helping with SOAR Apps development"""

app = typer.Typer(
    rich_markup_mode="rich",
    help=HELP,
    context_settings=CONTEXT_SETTINGS,
)

app.add_typer(manifests, name="manifests")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
