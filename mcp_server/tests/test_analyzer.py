"""Unit tests for TestAnalyzer."""

import pytest

from soar_test_assistant.test_analyzer import TestAnalyzer


class TestTestAnalyzer:
    """Test suite for TestAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a TestAnalyzer instance."""
        return TestAnalyzer()

    def test_analyze_empty_output(self, analyzer):
        """Test analyzing empty output."""
        result = analyzer.analyze("", None)
        assert result["summary"]["passed"] == 0
        assert result["summary"]["failed"] == 0
        assert result["failures"] == []
        assert result["errors"] == []

    def test_extract_failures(self, analyzer):
        """Test extracting FAILED test cases."""
        output = """
        FAILED tests/test_example.py::test_something - AssertionError
        FAILED tests/test_other.py::test_another - ValueError
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 2
        assert result["failures"][0]["file"] == "tests/test_example.py"
        assert result["failures"][0]["test"] == "test_something"
        assert result["failures"][1]["file"] == "tests/test_other.py"
        assert result["failures"][1]["test"] == "test_another"

    def test_extract_errors(self, analyzer):
        """Test extracting ERROR test cases."""
        output = """
        ERROR tests/test_example.py::test_setup - ImportError
        """
        result = analyzer.analyze(output, None)
        assert len(result["errors"]) == 1
        assert result["errors"][0]["file"] == "tests/test_example.py"
        assert result["errors"][0]["test"] == "test_setup"

    def test_categorize_assertion_error(self, analyzer):
        """Test categorizing assertion errors."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        def test_something():
        >   assert 1 == 2
        E   AssertionError
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        assert result["failures"][0]["category"] == "assertion_error"
        assert result["failures"][0]["is_app_bug"] is True
        assert result["failures"][0]["is_sdk_bug"] is False

    def test_categorize_import_error(self, analyzer):
        """Test categorizing import errors."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        ImportError: No module named 'missing_module'
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        assert result["failures"][0]["category"] == "import_error"
        assert result["failures"][0]["is_app_bug"] is True

    def test_categorize_attribute_error(self, analyzer):
        """Test categorizing attribute errors."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        AttributeError: 'NoneType' object has no attribute 'foo'
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        assert result["failures"][0]["category"] == "attribute_error"

    def test_categorize_type_error(self, analyzer):
        """Test categorizing type errors."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        TypeError: expected str, got int
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        assert result["failures"][0]["category"] == "type_error"

    def test_categorize_fixture_error(self, analyzer):
        """Test categorizing fixture errors."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        fixture 'missing_fixture' not found
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        assert result["failures"][0]["category"] == "fixture_error"

    def test_suggest_import_fix(self, analyzer):
        """Test suggesting import error fixes."""
        output = """
        FAILED tests/test_example.py::test_something
        _{test_something}
        ModuleNotFoundError: No module named 'requests'
        """
        result = analyzer.analyze(output, None)
        assert len(result["failures"]) == 1
        fix = result["failures"][0]["suggested_fix"]
        assert fix["type"] == "import"
        assert "requests" in fix["description"]
        assert "uv add" in fix["command"]

    def test_extract_summary(self, analyzer):
        """Test extracting test summary."""
        output = "=== 5 failed, 10 passed, 2 skipped in 5.23s ==="
        result = analyzer.analyze(output, None)
        assert result["summary"]["failed"] == 5
        assert result["summary"]["passed"] == 10
        assert result["summary"]["skipped"] == 2

    def test_total_issues_count(self, analyzer):
        """Test total issues count."""
        output = """
        FAILED tests/test_1.py::test_a
        FAILED tests/test_2.py::test_b
        ERROR tests/test_3.py::test_c
        """
        result = analyzer.analyze(output, None)
        assert result["total_issues"] == 3

    def test_extract_missing_module(self, analyzer):
        """Test extracting missing module name."""
        missing = analyzer._extract_missing_module(
            "ModuleNotFoundError: No module named 'foobar'"
        )
        assert missing == "foobar"

    def test_extract_fixture_name(self, analyzer):
        """Test extracting fixture name."""
        fixture = analyzer._extract_fixture_name(
            "fixture 'my_fixture' not found"
        )
        assert fixture == "my_fixture"

    def test_extract_assert_line(self, analyzer):
        """Test extracting assertion line."""
        assert_line = analyzer._extract_assert_line(
            "assert 1 == 2"
        )
        assert assert_line == "1 == 2"
