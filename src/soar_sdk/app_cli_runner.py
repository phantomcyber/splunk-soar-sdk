import argparse
import inspect
import json
from pathlib import Path
from pprint import pprint
import typing
from typing import Optional, Any


from soar_sdk.input_spec import ActionParameter, AppConfig, InputSpecification
from soar_sdk.types import Action

if typing.TYPE_CHECKING:
    from .app import App


class AppCliRunner:
    """
    Runner for local run of the actions handling with the app.
    Generates subparsers for each action, which take in JSON files for parameters and assets.
    """

    def __init__(self, app: "App") -> None:
        self.app = app

    def parse_args(self, argv: Optional[list[str]] = None) -> argparse.Namespace:
        root_parser = argparse.ArgumentParser()

        subparsers = root_parser.add_subparsers(dest="action", title="Actions")
        subparsers.required = True
        for name, action in self.app.actions_provider.get_actions().items():
            parser = subparsers.add_parser(
                name,
                aliases=(action.meta.action.replace(" ", "-"),),
                help=action.meta.verbose,
            )
            parser.set_defaults(identifier=name)
            parser.set_defaults(action=action)

            needs_asset = "asset" in inspect.signature(action).parameters
            parser.set_defaults(needs_asset=needs_asset)
            if needs_asset:
                parser.add_argument(
                    "-a",
                    "--asset-file",
                    help="Path to the asset file",
                    type=Path,
                    required=True,
                )

            if action.params_class is not None:
                parser.add_argument(
                    "-p", "--param-file", help="Input parameter JSON file", type=Path
                )

        # By default, argv will be None and we'll fall back to sys.argv,
        # but making it possible to provide args makes this method unit testable.
        args = root_parser.parse_args(argv)

        asset_json: dict[str, Any] = {}
        if args.needs_asset:
            try:
                asset_json = json.loads(args.asset_file.read_text())
            except Exception as e:
                root_parser.error(
                    f"Unable to read asset JSON file {args.asset_file}: {e}"
                )

        chosen_action: Action = args.action
        parameter_list: list[ActionParameter] = []

        if chosen_action.params_class is not None:
            params_file: Path = args.param_file
            try:
                params_json = json.loads(params_file.read_text())
            except Exception as e:
                root_parser.error(
                    f"Unable to read parameter JSON file {params_file}: {e}"
                )

            try:
                param = chosen_action.params_class.parse_obj(params_json)
            except Exception as e:
                root_parser.error(
                    f"Unable to parse parameter JSON file {params_file}:\n{e}"
                )

            parameter_list.append(ActionParameter(**param.dict()))

        input_data = InputSpecification(
            action=args.identifier,
            identifier=args.identifier,
            # FIXME: Make these values real
            config=AppConfig(
                app_version="1.0.0",
                directory=".",
                main_module="example_connector.py",
                **asset_json,
            ),
            parameters=parameter_list,
        )
        args.raw_input_data = input_data.json()
        return args

    def run(self) -> None:
        args = self.parse_args()
        self.app.handle(args.raw_input_data)
        # FIXME: ActionResult mock isn't quite right. Choosing not to unit test this section
        # yet, because the test will need to be rewritten. We shouldn't be posting our results
        # into ActionResult.param...
        for result in (
            self.app.actions_provider.soar_client.get_action_results()
        ):  # pragma: no cover
            pprint(result.param)
