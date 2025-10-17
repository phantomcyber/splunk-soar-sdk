from soar_sdk.input_spec import InputSpecification, AppConfig


def test_input_spec_without_action():
    """InputSpecification can be created without the action field."""
    input_spec = InputSpecification(
        asset_id="1",
        identifier="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
    )
    assert input_spec.action is None
    assert input_spec.identifier == "test_action"


def test_input_spec_with_action():
    """InputSpecification can be created with the action field."""
    input_spec = InputSpecification(
        asset_id="1",
        identifier="test_action",
        action="test_action",
        config=AppConfig(
            app_version="1.0.0", directory=".", main_module="example_connector.py"
        ),
    )
    assert input_spec.action == "test_action"
    assert input_spec.identifier == "test_action"
