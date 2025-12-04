import textwrap
from unittest import mock

import pytest

from soar_sdk.cli.manifests.processors import ManifestProcessor


class TestGetTargetPythonVersions:
    """Test the get_target_python_versions method that determines which Python versions to build for."""

    @pytest.fixture
    def mock_pyproject_toml(self, tmp_path):
        """Create a temporary directory for test pyproject.toml files."""
        return tmp_path

    def test_both_versions_when_no_constraint(self, mock_pyproject_toml):
        """When no requires-python is specified, should return all SDK-supported versions."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            """
        )
        (mock_pyproject_toml / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor(
            "manifest.json", project_context=str(mock_pyproject_toml)
        )
        versions = processor.get_target_python_versions()

        assert versions == ["3.13", "3.14"]

    def test_only_313_when_constrained(self, mock_pyproject_toml):
        """When requires-python excludes 3.14, should return only 3.13."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            requires-python = ">=3.13, <3.14"
            """
        )
        (mock_pyproject_toml / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor(
            "manifest.json", project_context=str(mock_pyproject_toml)
        )
        versions = processor.get_target_python_versions()

        assert versions == ["3.13"]

    def test_only_314_when_constrained(self, mock_pyproject_toml):
        """When requires-python excludes 3.13, should return only 3.14."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            requires-python = ">=3.14"
            """
        )
        (mock_pyproject_toml / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor(
            "manifest.json", project_context=str(mock_pyproject_toml)
        )
        versions = processor.get_target_python_versions()

        assert versions == ["3.14"]

    def test_both_versions_with_inclusive_range(self, mock_pyproject_toml):
        """When requires-python includes both 3.13 and 3.14, should return both."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            requires-python = ">=3.13, <=3.14"
            """
        )
        (mock_pyproject_toml / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor(
            "manifest.json", project_context=str(mock_pyproject_toml)
        )
        versions = processor.get_target_python_versions()

        assert versions == ["3.13", "3.14"]

    def test_empty_when_no_match(self, mock_pyproject_toml):
        """When requires-python doesn't match any SDK versions, should return empty."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            requires-python = ">=3.15"
            """
        )
        (mock_pyproject_toml / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor(
            "manifest.json", project_context=str(mock_pyproject_toml)
        )
        versions = processor.get_target_python_versions()

        assert versions == []


class TestResolveDependencies:
    """Test the resolve_dependencies method that determines which wheels to include."""

    @pytest.fixture
    def mock_package(self):
        """Create a mock package with resolve methods that return DependencyWheel objects."""
        from soar_sdk.meta.dependencies import DependencyWheel, UvWheel

        package = mock.Mock()

        # Create proper DependencyWheel objects
        wheel_313 = DependencyWheel(
            module="test_package",
            input_file="test_package-1.0.0-cp313-cp313-manylinux.whl",
            wheel=UvWheel(
                filename="test_package-1.0.0-cp313-cp313-manylinux.whl",
                hash="sha256:abc123",
            ),
        )
        wheel_314 = DependencyWheel(
            module="test_package",
            input_file="test_package-1.0.0-cp314-cp314-manylinux.whl",
            wheel=UvWheel(
                filename="test_package-1.0.0-cp314-cp314-manylinux.whl",
                hash="sha256:def456",
            ),
        )

        package.resolve_py313.return_value = wheel_313
        package.resolve_py314.return_value = wheel_314

        return package, wheel_313, wheel_314

    def test_resolve_both_versions_by_default(self, mock_package):
        """When no python_versions specified, should resolve both 3.13 and 3.14."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        py313_deps, py314_deps = UvLock.resolve_dependencies([package])

        package.resolve_py313.assert_called_once()
        package.resolve_py314.assert_called_once()
        assert len(py313_deps.wheel) == 1
        assert len(py314_deps.wheel) == 1
        # Should use version-specific prefixes since wheels are different
        assert "python313" in py313_deps.wheel[0].input_file
        assert "python314" in py314_deps.wheel[0].input_file

    def test_resolve_only_313(self, mock_package):
        """When python_versions=["3.13"], should only resolve 3.13."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.13"]
        )

        package.resolve_py313.assert_called_once()
        package.resolve_py314.assert_not_called()
        assert len(py313_deps.wheel) == 1
        assert len(py314_deps.wheel) == 0
        # Should use shared prefix since only one version
        assert "shared" in py313_deps.wheel[0].input_file

    def test_resolve_only_314(self, mock_package):
        """When python_versions=["3.14"], should only resolve 3.14."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.14"]
        )

        package.resolve_py313.assert_not_called()
        package.resolve_py314.assert_called_once()
        assert len(py313_deps.wheel) == 0
        assert len(py314_deps.wheel) == 1
        # Should use shared prefix since only one version
        assert "shared" in py314_deps.wheel[0].input_file

    def test_shared_prefix_when_wheels_identical(self):
        """When both versions resolve to identical wheels, should use 'shared' prefix."""
        from soar_sdk.meta.dependencies import DependencyWheel, UvLock, UvWheel

        package = mock.Mock()

        # Create identical wheels
        identical_wheel = DependencyWheel(
            module="test_package",
            input_file="test_package-1.0.0-py3-none-any.whl",
            wheel=UvWheel(
                filename="test_package-1.0.0-py3-none-any.whl",
                hash="sha256:same",
            ),
        )

        package.resolve_py313.return_value = identical_wheel
        package.resolve_py314.return_value = identical_wheel

        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.13", "3.14"]
        )

        # Both should use shared prefix
        assert "shared" in py313_deps.wheel[0].input_file
        assert "shared" in py314_deps.wheel[0].input_file

    def test_version_specific_prefix_when_wheels_different(self, mock_package):
        """When wheels differ between versions, should use version-specific prefixes."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.13", "3.14"]
        )

        # Should use version-specific prefixes since wheels are different
        assert "python313" in py313_deps.wheel[0].input_file
        assert "python314" in py314_deps.wheel[0].input_file

    def test_shared_prefix_when_only_one_version(self, mock_package):
        """When only one version is requested, should use 'shared' prefix."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.13"]
        )

        assert len(py313_deps.wheel) == 1
        assert "shared" in py313_deps.wheel[0].input_file

    def test_empty_list_for_unresolved_version(self, mock_package):
        """When a version is not in python_versions, its dependency list should be empty."""
        from soar_sdk.meta.dependencies import UvLock

        package, wheel_313, wheel_314 = mock_package

        # Only resolve 3.13
        py313_deps, py314_deps = UvLock.resolve_dependencies(
            [package], python_versions=["3.13"]
        )

        # 3.14 list should be empty
        assert len(py314_deps.wheel) == 0
        assert py314_deps.wheel == []


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_313_only_project_skips_314_resolution(self, tmp_path):
        """Test that a project with requires-python='>=3.13, <3.14' doesn't try to resolve 3.14 wheels."""
        pyproject_content = textwrap.dedent(
            """
            [project]
            name = "test-app"
            version = "1.0.0"
            requires-python = ">=3.13, <3.14"
            dependencies = ["httpx"]
            """
        )
        (tmp_path / "pyproject.toml").write_text(pyproject_content)

        processor = ManifestProcessor("manifest.json", project_context=str(tmp_path))
        versions = processor.get_target_python_versions()

        # Should only get 3.13
        assert versions == ["3.13"]

        # Verify this would be passed to resolve_dependencies
        # (actual resolution would happen in build(), but we can verify the input)
        assert "3.14" not in versions
