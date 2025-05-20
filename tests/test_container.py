#!/usr/bin/python

from soar_sdk.container import Container
from soar_sdk.artifact import Artifact


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


def test_container_attribute_setting():
    """Test Container attribute setting."""
    container = Container(name="Test Container", label="case")

    container.status = "new"
    assert container.status == "new"
    assert container.to_dict()["status"] == "new"


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
        data={"ip": "192.168.1.1", "hostname": "test.local"},
    )

    artifact_dict = artifact.to_dict()
    assert artifact_dict["name"] == "Custom Artifact"
    assert artifact_dict["label"] == "event"
    assert artifact_dict["type"] == "host"
    assert artifact_dict["data"]["ip"] == "192.168.1.1"
    assert artifact.data["hostname"] == "test.local"


def test_artifact_attribute_setting():
    """Test Artifact attribute setting."""
    artifact = Artifact(name="Custom Artifact")

    artifact.severity = "high"
    assert artifact.severity == "high"
    assert artifact.to_dict()["severity"] == "high"
