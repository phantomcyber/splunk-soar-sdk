from soar_sdk.meta.adapters import TOMLDataAdapter
from soar_sdk.meta.app import AppMeta


def test_loading_toml_file():
    meta: AppMeta = TOMLDataAdapter.load_data("tests/example_app/pyproject.toml")
    assert meta.main_module == "src.app:app"
    assert meta.package_name == "phantom_exampleapp"
