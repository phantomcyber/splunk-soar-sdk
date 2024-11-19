import importlib
import json
from datetime import datetime
from pathlib import Path
from pprint import pprint

from soar_sdk.app import App
from soar_sdk.cli.manifests.path_utils import context_directory
from soar_sdk.meta.adapters import TOMLDataAdapter
from soar_sdk.meta.app import AppMeta


class ManifestProcessor:
    def __init__(self, manifest_path: str, project_context: str = "."):
        self.manifest_path = manifest_path
        self.project_context = Path(project_context)

    def build(self) -> AppMeta:
        """
        Builds full AppMeta information including actions and other extra fields
        """
        app_meta: AppMeta = self.load_toml_app_meta()
        app = self.import_app_instance(app_meta)
        app_meta.actions = app.actions_provider.get_actions_meta_list()
        app_meta.utctime_updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        return app_meta

    def create(self) -> None:
        """
        Creates the App Manifest JSON information with all sources
        and save it back to the manifest file.
        """
        app_meta = self.build()
        pprint(app_meta.dict())

        self.save_json_manifest(app_meta)

    def load_toml_app_meta(self) -> AppMeta:
        return TOMLDataAdapter.load_data(
            f"{self.project_context.as_posix()}/pyproject.toml"
        )

    def save_json_manifest(self, app_meta: AppMeta) -> None:
        with open(self.manifest_path, "w") as f:
            json.dump(app_meta.dict(), f, indent=4)

    def import_app_instance(self, app_meta: AppMeta) -> App:
        module_name = ".".join(app_meta.app_module.split(".")[:-1])
        app_instance_name = app_meta.app_module.split(".")[-1]

        with context_directory(self.project_context):
            # operate as if running in the project context directory
            package_name = Path.cwd().name
            app_module = importlib.import_module(f"{package_name}.{module_name}")
            app = getattr(app_module, app_instance_name)
        return app
