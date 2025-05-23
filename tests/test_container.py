from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact


def test_container_basic():
    """Test basic Container functionality."""
    container = Container(
        name="Test Container",
        label="alert",
        description="Test Description",
        source_data_identifier="test_1234",
        severity="medium",
    )

    container_dict = container.to_dict()
    assert container_dict["name"] == "Test Container"
    assert container_dict["label"] == "alert"
    assert container_dict["description"] == "Test Description"
    assert container_dict["source_data_identifier"] == "test_1234"
    assert container_dict["severity"] == "medium"


def test_container_invalid_attribute():
    """Test setting an invalid attribute should raise ValidationError."""
    from pydantic import ValidationError
    import pytest

    try:
        Container(name="Test Container", not_allowed="fail")
        pytest.fail("Setting an invalid attribute should raise ValidationError")
    except ValidationError:
        pass


def test_container_missing_required_field():
    """Test that missing required fields raises ValidationError."""
    from pydantic import ValidationError
    import pytest

    try:
        Container()
        pytest.fail("Missing required field 'name' should raise ValidationError")
    except ValidationError:
        pass


def test_container_type_validation():
    """Test that invalid types raise ValidationError."""
    from pydantic import ValidationError
    import pytest

    try:
        Container(name={"invalid": "type"})
        pytest.fail("Invalid type for 'name' should raise ValidationError")
    except ValidationError:
        pass


def test_container_default_values():
    """Test that default values are set correctly."""
    container = Container(name="Test Container")
    assert container.run_automation is False
    assert container.to_dict()["run_automation"] is False


def test_container_serialization_deserialization():
    """Test serialization and deserialization."""
    data = {
        "name": "Test Container",
        "label": "alert",
        "severity": "medium",
    }
    container = Container(**data)
    container_dict = container.to_dict()
    new_container = Container(**container_dict)
    assert new_container == container


def test_artifact_basic():
    """Test basic Artifact functionality."""
    artifact = Artifact(
        name="Test Artifact",
        label="alert",
        description="Test Description",
        type="network",
        severity="medium",
    )

    artifact_dict = artifact.to_dict()
    assert artifact_dict["name"] == "Test Artifact"
    assert artifact_dict["label"] == "alert"
    assert artifact_dict["description"] == "Test Description"
    assert artifact_dict["type"] == "network"
    assert artifact_dict["severity"] == "medium"


def test_artifact_with_data():
    """Test Artifact with data property."""
    artifact = Artifact(
        name="Custom Artifact",
        label="event",
        type="host",
        data={"ip": "192.168.0.1", "hostname": "test.local"},
    )

    artifact_dict = artifact.to_dict()
    assert artifact_dict["name"] == "Custom Artifact"
    assert artifact_dict["label"] == "event"
    assert artifact_dict["type"] == "host"
    assert artifact_dict["data"]["ip"] == "192.168.0.1"
    assert artifact.data["hostname"] == "test.local"


def test_artifact_invalid_attribute():
    """Test setting an invalid attribute should raise ValidationError."""
    from pydantic import ValidationError
    import pytest

    try:
        Artifact(name="Test Artifact", not_allowed="fail")
        pytest.fail("Setting an invalid attribute should raise ValidationError")
    except ValidationError:
        pass


def test_artifact_type_validation():
    """Test that invalid types raise ValidationError for Artifact."""
    from pydantic import ValidationError
    import pytest

    try:
        Artifact(name={"invalid": "type"})
        pytest.fail("Invalid type for 'name' should raise ValidationError")
    except ValidationError:
        pass


def test_artifact_default_values():
    """Test that default values are set correctly for Artifact."""
    artifact = Artifact()
    assert artifact.run_automation is False
    assert artifact.to_dict()["run_automation"] is False


def test_artifact_serialization_deserialization():
    """Test serialization and deserialization."""
    data = {
        "name": "Test Artifact",
        "label": "alert",
        "severity": "medium",
    }
    artifact = Artifact(**data)
    artifact_dict = artifact.to_dict()
    new_artifact = Artifact(**artifact_dict)
    assert new_artifact == artifact
