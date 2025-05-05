import toml

from .app import AppMeta


class TOMLDataAdapter:
    @staticmethod
    def load_data(filepath: str) -> AppMeta:
        with open(filepath) as f:
            toml_data = toml.load(f)

        uv_app_data = toml_data.get("project", {})

        return AppMeta(
            **dict(
                name=uv_app_data.get("name"),
                description=uv_app_data.get("description"),
                app_version=uv_app_data.get("version"),
                license=uv_app_data.get("license"),
            )
        )
