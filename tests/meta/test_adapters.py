from soar_sdk.meta.adapters import TOMLDataAdapter
from soar_sdk.meta.app import AppMeta


def test_loading_toml_file():
    meta: AppMeta = TOMLDataAdapter.load_data("example_app/pyproject.toml")
    assert meta.app_module == "src.app.app"
    assert meta.name == "Example Application"
