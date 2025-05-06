import toml

from .app import AppMeta


class TOMLDataAdapter:
    @staticmethod
    def load_data(filepath: str) -> AppMeta:
        with open(filepath) as f:
            toml_data = toml.load(f)

        soar_app_data = toml_data.get("tool", {}).get("soar", {}).get("app", {})
        uv_app_data = toml_data.get("project", {})
        package_name = uv_app_data.get("name")
        package_name = (
            f"phantom_{package_name}"
            if package_name and not package_name.startswith("phantom_")
            else package_name
        )

        return AppMeta(
            **dict(
                description=uv_app_data.get("description"),
                app_version=uv_app_data.get("version"),
                license=uv_app_data.get("license"),
                package_name=package_name,
                **soar_app_data,
            )
        )
