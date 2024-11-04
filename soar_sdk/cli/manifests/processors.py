import importlib
import json
import os
from datetime import datetime
from pprint import pprint

from soar_sdk.app import App
from soar_sdk.meta.adapters import TOMLDataAdapter
from soar_sdk.meta.app import AppMeta


class ManifestProcessor:

    def __init__(self, json_filename, project_context: str = "."):
        self.json_filename = json_filename
        self.project_context = project_context

    def create(self):
        """
        Creates the App Manifest JSON information with all sources
        and save it back to the manifest file.
        """
        app_meta: AppMeta = self.load_toml_app_meta()
        app = self.import_app_instance(app_meta)
        app_meta.actions = self.get_actions_list(app)

        app_meta.utctime_updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        pprint(app_meta.dict())

        self.save_json_manifest(app_meta.dict())

    def save_json_manifest(self, data: dict):  # pragma: no cover
        with open(self.json_filename, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def get_actions_list(app: App):
        return app.manager.get_actions().items()

    def load_toml_app_meta(self) -> AppMeta:
        return TOMLDataAdapter.load_data(f"{self.project_context}/pyproject.toml")

    def import_app_instance(self, app_meta: AppMeta) -> App:
        module_name = ".".join(app_meta.app_module.split(".")[:-1])
        app_instance_name = app_meta.app_module.split(".")[-1]
        package_name = self.get_package_name()
        app_module = importlib.import_module(f"{package_name}.{module_name}")
        app = getattr(app_module, app_instance_name)
        return app

    def get_package_name(self):
        if self.project_context == ".":
            package_path = os.getcwd()
        else:
            package_path = self.project_context

        return package_path.split("/")[-1]
