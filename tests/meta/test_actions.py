import pytest
from pydantic import ValidationError

from soar_sdk.meta.actions import ActionLock, ActionMeta


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

    result = meta.model_dump()

    assert "render" in result
    assert result["render"]["type"] == "custom"
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

    result = meta.model_dump()

    assert result["render"]["type"] == "custom"
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

    result = meta.model_dump()

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

    result = meta.model_dump()

    assert "lock" in result
    assert result["lock"]["enabled"] is True
    assert "enable_concurrency_lock" not in result


def test_action_meta_dict_with_complete_lock_metadata():
    """Test serialization of the complete action synchronization schema."""
    meta = ActionMeta(
        action="test_action",
        identifier="test_identifier",
        description="Test description",
        type="generic",
        read_only=False,
        lock=ActionLock(
            concurrency=False,
            data_path="configuration.server",
            timeout=600,
        ),
    )

    result = meta.model_dump()

    assert result["lock"] == {
        "enabled": True,
        "concurrency": False,
        "data_path": "configuration.server",
        "timeout": 600,
    }


def test_action_meta_rejects_ambiguous_lock_configuration():
    """Test that the legacy flag cannot be combined with typed lock metadata."""
    with pytest.raises(
        ValidationError,
        match="lock and enable_concurrency_lock cannot both be configured",
    ):
        ActionMeta(
            action="test_action",
            identifier="test_identifier",
            description="Test description",
            type="generic",
            read_only=False,
            lock=ActionLock(concurrency=False),
            enable_concurrency_lock=True,
        )


def test_action_lock_requires_positive_timeout():
    """Test that invalid lock acquisition timeouts are rejected."""
    with pytest.raises(ValidationError):
        ActionLock(timeout=0)
