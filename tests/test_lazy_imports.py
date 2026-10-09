import ast
import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SDK_SOURCE = Path(__file__).resolve().parents[1] / "src" / "soar_sdk"


def _run_python(script, *, eager=False, mode=None):
    prefix = ""
    if eager:
        prefix = "import sys\nif hasattr(sys, 'set_lazy_imports_filter'):\n sys.set_lazy_imports_filter(lambda importer, imported, fromlist: False)\n"
    result = subprocess.run(
        [
            sys.executable,
            *(["-X", f"lazy_imports={mode}"] if mode is not None else []),
            "-c",
            prefix + textwrap.dedent(script),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("path", sorted(SDK_SOURCE.rglob("*.py")))
def test_sdk_declares_all_eligible_module_imports_lazy(path):
    tree = ast.parse(path.read_text())
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    declarations = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "__lazy_modules__"
    }
    package = ".".join(("soar_sdk", *path.parent.relative_to(SDK_SOURCE).parts))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        ancestor = parents.get(node)
        while ancestor is not None and not isinstance(
            ancestor,
            ast.FunctionDef
            | ast.AsyncFunctionDef
            | ast.ClassDef
            | ast.Try
            | ast.TryStar,
        ):
            ancestor = parents.get(ancestor)
        if ancestor is not None:
            continue
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            if node.module == "__future__" or any(
                alias.name == "*" for alias in node.names
            ):
                continue
            names = [
                importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
            ]
        assert set(names) <= declarations.get("__lazy_modules__", set()), path


@pytest.mark.parametrize("eager", [False, True])
@pytest.mark.parametrize("mode", [None, "normal", "all"])
@pytest.mark.parametrize(
    "module, symbol, dependency",
    [
        ("soar_sdk.auth", "SOARAssetOAuthClient", "soar_sdk.auth.client"),
        ("soar_sdk.models", "Artifact", "soar_sdk.models.artifact"),
        ("soar_sdk.meta.dependencies", "UvLock", "soar_sdk.meta.dependencies.lock"),
        ("soar_sdk.decorators", "ActionDecorator", "soar_sdk.decorators.action"),
    ],
)
def test_public_exports_load_on_first_use_in_fresh_process(
    module, symbol, dependency, eager, mode
):
    _run_python(
        f"""
        import importlib
        import sys
        import types

        before_mode = sys.get_lazy_imports() if hasattr(sys, "get_lazy_imports") else None
        before_filter = sys.get_lazy_imports_filter() if hasattr(sys, "get_lazy_imports_filter") else None
        module = importlib.import_module({module!r})
        lazy = sys.version_info >= (3, 15) and not {eager!r}
        assert ({dependency!r} not in sys.modules) == lazy
        if lazy:
            assert type(vars(module)[{symbol!r}]) is types.LazyImportType
        exported = getattr(module, {symbol!r})
        assert {dependency!r} in sys.modules
        assert exported is getattr(sys.modules[{dependency!r}], {symbol!r})
        if before_mode is not None:
            assert sys.get_lazy_imports() == before_mode
            assert sys.get_lazy_imports_filter() is before_filter
        """,
        eager=eager,
        mode=mode,
    )


@pytest.mark.parametrize("eager", [False, True])
def test_lazily_imported_models_validate_data(eager):
    _run_python(
        """
        from soar_sdk.models import Artifact
        artifact = Artifact(name="Lazy import test", cef={"sourceAddress": "192.0.2.1"})
        assert artifact.model_dump()["cef"]["sourceAddress"] == "192.0.2.1"
        """,
        eager=eager,
    )


def test_app_registers_action_in_fresh_process():
    _run_python(
        """
        from soar_sdk.action_results import ActionOutput
        from soar_sdk.app import App
        from soar_sdk.params import Params

        app = App(
            name="lazy_app",
            appid="9b388c08-67de-4ca4-817f-26f8fb7cbf55",
            app_type="sandbox",
            logo="logo.svg",
            logo_dark="logo_dark.svg",
            product_vendor="Splunk",
            product_name="Example App",
            publisher="Splunk",
        )

        class EchoParams(Params):
            value: str

        class EchoOutput(ActionOutput):
            value: str

        @app.action(name="Echo", identifier="echo")
        def echo(params: EchoParams) -> EchoOutput:
            return EchoOutput(value=params.value)

        actions = app.actions_manager.get_actions_meta_list()
        assert len(actions) == 1
        assert actions[0].identifier == "echo"
        assert actions[0].parameters is EchoParams
        assert echo(EchoParams(value="registered")) is True
        assert app.actions_manager.get_results()[0].get_data() == [{"value": "registered"}]
        """
    )


@pytest.mark.parametrize(
    "args",
    [["--help"], ["version"], ["init", "--help"], ["package", "build", "--help"]],
)
def test_cli_runs_in_fresh_process(args):
    _run_python(
        f"""
        import sys
        from soar_sdk.cli.cli import main

        sys.argv = ["soarapps", *{args!r}]
        main()
        """
    )


@pytest.mark.parametrize("available", [True, False])
def test_optional_platform_imports_preserve_fallbacks(available):
    _run_python(
        f"""
        import sys
        import types

        phantom = types.ModuleType("phantom")
        phantom.__path__ = []
        sys.modules["phantom"] = phantom
        platform = types.ModuleType("phantom.base_connector")
        sys.modules["phantom.base_connector"] = platform
        if {available!r}:
            platform.BaseConnector = type("PlatformBaseConnector", (), {{}})

        import soar_sdk.shims.phantom.base_connector as shim
        assert shim._soar_is_available is {available!r}
        if {available!r}:
            assert shim.BaseConnector is platform.BaseConnector
        else:
            assert shim.BaseConnector.__module__ == "soar_sdk.shims.phantom.base_connector"
        """
    )


@pytest.mark.skipif(
    sys.version_info < (3, 15), reason="Native lazy-import filters require Python 3.15"
)
def test_sdk_preserves_application_lazy_import_filter():
    _run_python(
        """
        import sys

        def application_filter(importer, imported, fromlist):
            return imported != "soar_sdk.auth.client"

        sys.set_lazy_imports_filter(application_filter)
        import soar_sdk.auth
        assert "soar_sdk.auth.client" in sys.modules
        assert sys.get_lazy_imports() == "normal"
        assert sys.get_lazy_imports_filter() is application_filter
        """
    )
