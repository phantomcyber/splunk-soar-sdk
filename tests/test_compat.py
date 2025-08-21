import pytest
from soar_sdk.compat import remove_when_soar_newer_than, PythonVersion


def test_raises_runtime_error_when_version_below_minimum():
    """Test that function raises RuntimeError when version is below minimum."""
    with pytest.raises(RuntimeError, match="Support for SOAR 1.0.0 is over"):
        remove_when_soar_newer_than("1.0.0", base_version="2.0.0")


def test_raises_runtime_error_with_custom_message():
    """Test that function raises RuntimeError with custom message."""
    custom_message = "Custom deprecation message"
    with pytest.raises(RuntimeError, match=custom_message):
        remove_when_soar_newer_than("1.5.0", custom_message, base_version="2.0.0")


@pytest.mark.parametrize("version", ("2.0.0", "2.1.0", "3.0.0"))
def test_no_error_when_version_equals_or_above_minimum(version):
    """Test that no error is raised when version equals or is above minimum."""
    # Should not raise any exception
    remove_when_soar_newer_than(version, base_version="2.0.0")


def test_str_python_version():
    """Test that PythonVersion enum returns correct string representation."""
    assert str(PythonVersion.PY_3_9) == "3.9"
    assert str(PythonVersion.PY_3_13) == "3.13"


@pytest.mark.parametrize(
    "versions, expected_requires_python",
    (
        ([], ">=3.9, <3.14"),
        ([PythonVersion.PY_3_9], ">=3.9, <3.10"),
        ([PythonVersion.PY_3_13], ">=3.13, <3.14"),
        ([PythonVersion.PY_3_9, PythonVersion.PY_3_13], ">=3.9, <3.14"),
        (PythonVersion.all(), ">=3.9, <3.14"),
    ),
)
def test_to_requires_python(
    versions: list[PythonVersion], expected_requires_python: str
):
    """Test that to_requires_python converts PythonVersion to PEP-508 compatible string."""
    actual_requires_python = PythonVersion.to_requires_python(versions)
    assert actual_requires_python == expected_requires_python
