from soar_sdk.meta.actions import ActionMeta


def test_action_meta_dict_with_view_handler():
    """Test ActionMeta.dict() with view_handler to cover the else branch for module_parts."""

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
        view_handler=mock_view,
    )

    result = meta.dict()

    assert result["render"]["view"] == "single_module.mock_view"
    assert "view_handler" not in result


def test_action_meta_dict_with_view_handler_multi_part_module():
    """Test ActionMeta.dict() with view_handler having multi-part module name."""

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
        view_handler=mock_view,
    )

    result = meta.dict()

    assert result["render"]["view"] == "src.app.mock_view"
    assert "view_handler" not in result


def test_action_meta_dict_without_view_handler():
    """Test ActionMeta.dict() without view_handler."""

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
    assert "view_handler" not in result


def test_action_meta_dict_with_concurrency_lock():
    """Test ActionMeta.dict() with enable_concurrency_lock set to True."""

    meta = ActionMeta(
        action="test_action",
        identifier="test_identifier",
        description="Test description",
        verbose="Test verbose",
        type="generic",
        read_only=True,
        versions="EQ(*)",
        enable_concurrency_lock=True,
    )

    result = meta.dict()

    assert "lock" in result
    assert result["lock"]["enabled"] is True
    assert "enable_concurrency_lock" not in result
