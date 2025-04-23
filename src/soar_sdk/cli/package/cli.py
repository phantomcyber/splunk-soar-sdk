import typer

import tarfile
from io import BytesIO
import json
from pathlib import Path

from typing import Optional

from soar_sdk.cli.manifests.processors import ManifestProcessor
from soar_sdk.cli.path_utils import context_directory


package = typer.Typer()


@package.command()
def build(output_file: str, project_context: str) -> None:
    output_path = Path(output_file)
    with context_directory(Path(project_context)):
        app_meta = ManifestProcessor("app.json", ".").build()
        app_name = app_meta.name

        def filter_source_files(t: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
            if t.isdir() and "__pycache__" not in t.name:
                return t
            if t.isfile() and t.name.endswith(".py"):
                return t
            return None

        with tarfile.open(output_path, "w:gz") as app_tarball:
            manifest_json = json.dumps(app_meta.dict(), indent=4).encode()
            manifest_info = tarfile.TarInfo(f"{app_name}/{app_name}.json")
            manifest_info.size = len(manifest_json)
            app_tarball.addfile(manifest_info, BytesIO(manifest_json))

            for wheel in (
                app_meta.pip39_dependencies.wheels + app_meta.pip313_dependencies.wheels
            ):
                for path, data in wheel.collect_wheels():
                    info = tarfile.TarInfo(f"{app_name}/{path}")
                    info.size = len(data)
                    app_tarball.addfile(info, BytesIO(data))

            app_tarball.add(app_meta.logo, f"{app_name}/{app_meta.logo}")
            app_tarball.add(app_meta.logo_dark, f"{app_name}/{app_meta.logo_dark}")

            app_tarball.add(
                "src", f"{app_name}/src", recursive=True, filter=filter_source_files
            )
