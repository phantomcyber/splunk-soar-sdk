import typer

import tarfile
from io import BytesIO
import json
from pathlib import Path

from typing import Optional

from soar_sdk.cli.manifests.processors import ManifestProcessor
from soar_sdk.meta.dependencies import DependencyWheel
from soar_sdk.cli.path_utils import context_directory


package = typer.Typer(invoke_without_command=True)


@package.callback()
def callback() -> None:
    pass


@package.command()
def build(
    output_file: str, project_context: str, with_sdk_wheel_from: str = ""
) -> None:
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
            for wheel in (
                app_meta.pip39_dependencies.wheel + app_meta.pip313_dependencies.wheel
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

            if with_sdk_wheel_from != "":
                wheel_path = Path(with_sdk_wheel_from)
                wheel_name = wheel_path.name

                wheel_archive_path = f"wheels/shared/{wheel_name}"
                app_tarball.add(wheel_path, f"{app_name}/{wheel_archive_path}")

                wheel_entry = DependencyWheel(
                    module="soar_sdk",
                    input_file=wheel_archive_path,
                    input_file_aarch64=wheel_archive_path,
                )
                app_meta.pip39_dependencies.wheel.append(wheel_entry)
                app_meta.pip313_dependencies.wheel.append(wheel_entry)

            manifest_json = json.dumps(app_meta.dict(), indent=4).encode()
            manifest_info = tarfile.TarInfo(f"{app_name}/{app_name}.json")
            manifest_info.size = len(manifest_json)
            app_tarball.addfile(manifest_info, BytesIO(manifest_json))
