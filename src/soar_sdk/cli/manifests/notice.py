import json
import shutil
import subprocess
from pathlib import Path

import typer
from rich import print as rprint

from soar_sdk.cli.manifests.processors import ManifestProcessor

LINE_SEPARATOR = (
    "@@@@============================================================================"
)


class NoticeGenerator:
    """Generates a NOTICE file with third-party license attributions for a SOAR app."""

    def __init__(self, project_context: Path) -> None:
        self.project_context = Path(project_context)

    def get_app_name_and_license(self) -> tuple[str, str]:
        """Import the app instance to get the display name; get license from pyproject.toml."""
        processor = ManifestProcessor("", str(self.project_context))
        app_meta = processor.load_toml_app_meta()
        app = processor.import_app_instance(app_meta)
        return str(app.app_meta_info["name"]), app_meta.license

    def get_dependency_names(self) -> list[str]:
        """Return the transitive runtime dependency names from uv.lock."""
        processor = ManifestProcessor("", str(self.project_context))
        app_meta = processor.load_toml_app_meta()
        uv_lock = processor.load_app_uv_lock()
        packages = uv_lock.build_package_list(app_meta.project_name)
        return [pkg.name for pkg in packages]

    def get_license_info(self, package_names: list[str]) -> list[dict]:
        """Run pip-licenses in the app's venv and return parsed license data."""
        uv_path = shutil.which("uv")
        if not uv_path:
            rprint("[red]uv command not found. Please install uv to continue.[/]")
            raise typer.Exit(code=1)

        cmd = [
            uv_path,
            "run",
            "pip-licenses",
            "--format=json",
            "--with-license-file",
            "--no-license-path",
            "--with-urls",
            "--with-notice-file",
            "--packages",
            *package_names,
        ]
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=self.project_context,
        )
        entries: list[dict] = json.loads(result.stdout)
        for entry in entries:
            if entry.get("LicenseText") == "UNKNOWN":
                entry["LicenseText"] = None
            if entry.get("NoticeText") == "UNKNOWN":
                entry["NoticeText"] = None
        return entries

    def _format_notice(
        self,
        app_name: str,
        app_license: str,
        license_entries: list[dict],
    ) -> str:
        """Build the full NOTICE file content."""
        lines: list[str] = [f"Splunk SOAR App: {app_name}\n{app_license}\n"]

        if not license_entries:
            return "".join(lines)

        lines.append("Third Party Software Attributions:\n")

        for entry in license_entries:
            name = entry.get("Name", "")
            version = entry.get("Version", "")
            url = entry.get("URL", "")
            license_name = entry.get("License", "")
            license_text = (
                entry.get("LicenseText")
                or f"Please navigate to {url} to obtain a copy of the license."
            )
            notice_text = entry.get("NoticeText")

            notice_block = f"\nNotice:\n\n{notice_text}" if notice_text else ""

            lines.append(
                f"\n{LINE_SEPARATOR}\n\n"
                f"Library: {name} - {version}\n"
                f"Homepage: {url}\n"
                f"License: {license_name}\n"
                f"License Text:\n\n"
                f"{license_text}"
                f"{notice_block}\n"
            )

        return "".join(lines)

    @staticmethod
    def _post_process(text: str) -> str:
        """Strip trailing whitespace from lines and trailing blank lines; end with a newline."""
        lines = [line.rstrip() for line in text.splitlines()]
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    def generate(self, output_path: Path) -> None:
        """Validate, collect license info, and write the NOTICE file."""
        pyproject = self.project_context / "pyproject.toml"
        uv_lock = self.project_context / "uv.lock"
        venv = self.project_context / ".venv"

        if not pyproject.exists():
            rprint(
                f"[red]No pyproject.toml found at {self.project_context}. Is this a SOAR app directory?[/]"
            )
            raise typer.Exit(code=1)
        if not uv_lock.exists():
            rprint(
                f"[red]No uv.lock found at {self.project_context}. Run 'uv lock' first.[/]"
            )
            raise typer.Exit(code=1)
        if not venv.exists():
            rprint(
                f"[red]No virtual environment found at {self.project_context}. Run 'uv sync' first.[/]"
            )
            raise typer.Exit(code=1)

        rprint("[blue]Loading app metadata...[/]")
        app_name, app_license = self.get_app_name_and_license()

        rprint("[blue]Resolving dependencies from uv.lock...[/]")
        package_names = self.get_dependency_names()

        license_entries: list[dict] = []
        if package_names:
            rprint("[blue]Collecting license information...[/]")
            try:
                license_entries = self.get_license_info(package_names)
            except subprocess.CalledProcessError as e:
                rprint(f"[red]Failed to collect license information: {e.stderr}[/]")
                raise typer.Exit(code=1) from e

        content = self._format_notice(app_name, app_license, license_entries)
        content = self._post_process(content)

        output_path.write_text(content)
        rprint(f"[green]NOTICE file written to {output_path}[/]")
