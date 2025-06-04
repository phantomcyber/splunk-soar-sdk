from soar_sdk.meta.actions import ActionMeta


def test_action_meta_dict_with_custom_view():
    """Test ActionMeta.dict() with custom_view to cover the else branch for module_parts."""

    def mock_view():
        pass

    # Mock the module to have only one part (no dots)
    mock_view.__module__ = "single_module"

    meta = ActionMeta(
        action="test_action",
        identifier="test_identifier",
        description="Test description",
        verbose="Test verbose",
        type="generic",
        read_only=True,
        versions="EQ(*)",
        custom_view=mock_view,
    )

    result = meta.dict()

    assert result["render"]["view"] == "single_module.mock_view"
    assert "custom_view" not in result


def test_action_meta_dict_with_custom_view_multi_part_module():
    """Test ActionMeta.dict() with custom_view having multi-part module name."""

    def mock_view():
        pass

    # Mock the module to have multiple parts
    mock_view.__module__ = "example_app.src.app"

    meta = ActionMeta(
        action="test_action",
        identifier="test_identifier",
        description="Test description",
        verbose="Test verbose",
        type="generic",
        read_only=True,
        versions="EQ(*)",
        custom_view=mock_view,
    )

    result = meta.dict()

    assert result["render"]["view"] == "src.app.mock_view"
    assert "custom_view" not in result


def test_action_meta_dict_without_custom_view():
    """Test ActionMeta.dict() without custom_view."""

    meta = ActionMeta(
        action="test_action",
        identifier="test_identifier",
        description="Test description",
        verbose="Test verbose",
        type="generic",
        read_only=True,
        versions="EQ(*)",
    )

    result = meta.dict()

    assert "render" not in result
    assert "custom_view" not in result
