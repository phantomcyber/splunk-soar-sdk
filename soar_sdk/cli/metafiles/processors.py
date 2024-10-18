import importlib
import json
import os
from datetime import datetime
from pprint import pprint

from soar_sdk.app import App
from soar_sdk.meta.adapters import TOMLDataAdapter
from soar_sdk.meta.app import AppMeta


class MetafileUpdateProcessor:

    def __init__(self, json_filename, project_context: str = "."):
        self.json_filename = json_filename
        self.project_context = project_context
        self.app_meta: AppMeta = self.load_toml_app_meta()

    def create(self):
        """
        Creates the App Meta information with all sources
        and save it back to the meta file.
        """

        app = self.get_app()
        self.update_actions(app)

        self.app_meta.utctime_updated = datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        pprint(self.app_meta.dict())

        with open(self.json_filename, "w") as f:
            json.dump(self.app_meta.dict(), f, indent=4)

    def update_actions(self, app):
        self.app_meta.actions = []
        for action_name, action in app.get_actions().items():
            self.app_meta.actions.append(action.meta)

    def load_toml_app_meta(self) -> AppMeta:
        return TOMLDataAdapter.load_data(f"{self.project_context}/pyproject.toml")

    def get_app(self) -> App:
        module_name = ".".join(self.app_meta.app_module.split(".")[:-1])
        app_instance_name = self.app_meta.app_module.split(".")[-1]
        if self.project_context == ".":
            path = os.getcwd()
        else:
            path = self.project_context
        cwd = path.split("/")[-1]
        app_module = importlib.import_module(f"{cwd}.{module_name}")
        app = getattr(app_module, app_instance_name)
        return app
