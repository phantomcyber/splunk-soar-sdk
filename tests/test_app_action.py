import pytest


def test_app_action_simple_declaration(simple_app):
    @simple_app.action()
    def some_handler(ctx): ...

    assert len(simple_app.manager.get_actions()) == 1
    assert "some_handler" in simple_app.manager.get_actions()


def test_action_decoration_with_meta(example_app):

    @example_app.action(name="Test Function", identifier="test_function_id")
    def foo(ctx):
        """
        This action does nothing for now.
        """
        pass

    assert sorted(foo.meta.dict().keys()) == sorted(
        [
            "action",
            "identifier",
            "description",
            "verbose",
            "type",
            "parameters",
            "read_only",
            "output",
            "versions",
        ]
    )

    assert foo.meta.action == "Test Function"
    assert foo.meta.description == "This action does nothing for now."
    assert example_app.manager.get_action("test_function_id") == foo


def test_action_decoration_uses_function_name_for_action_name(example_app):

    @example_app.action()
    def action_function(ctx):
        pass

    assert action_function.meta.action == "action function"


def test_action_decoration_uses_meta_identifier_for_action_name(example_app):

    @example_app.action(identifier="some_identifier")
    def action_function(ctx):
        pass

    assert action_function.meta.action == "some identifier"


def test_action_takes_no_app_ctx(example_app):

    with pytest.raises(TypeError):

        @example_app.action()
        def action_with_no_ctx():
            pass


def test_action_decorated_function_has_no_pydantic_model_specified(example_app):

    with pytest.raises(TypeError):

        @example_app.action()
        def action_with_no_typehints(ctx, params):
            pass


def test_action_decorated_function_has_params_non_pydantic_model_type(example_app):

    with pytest.raises(TypeError):

        @example_app.action()
        def action_with_no_pydantic_model_typehint(ctx, params: int):
            pass
