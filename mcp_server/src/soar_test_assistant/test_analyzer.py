"""Pytest test output analyzer for identifying failures and suggesting fixes."""

import re


class TestAnalyzer:
    def analyze(self, test_output: str, app_path: str | None = None) -> dict:
        """Analyze pytest output and categorize failures."""
        failures = self._extract_failures(test_output)
        errors = self._extract_errors(test_output)
        summary = self._extract_summary(test_output)

        analyzed_failures = []
        for failure in failures:
            analysis = self._analyze_failure(failure, app_path)
            analyzed_failures.append(analysis)

        analyzed_errors = []
        for error in errors:
            analysis = self._analyze_error(error, app_path)
            analyzed_errors.append(analysis)

        return {
            "summary": summary,
            "failures": analyzed_failures,
            "errors": analyzed_errors,
            "total_issues": len(analyzed_failures) + len(analyzed_errors),
        }

    def _extract_failures(self, output: str) -> list[dict]:
        """Extract FAILED test cases from pytest output."""
        failures = []
        failure_pattern = r"FAILED ([\w/\._-]+)::(\w+)"
        matches = re.findall(failure_pattern, output)

        for file_path, test_name in matches:
            failure_section = self._extract_failure_section(
                output, file_path, test_name
            )
            failures.append(
                {
                    "file": file_path,
                    "test": test_name,
                    "traceback": failure_section,
                }
            )

        return failures

    def _extract_errors(self, output: str) -> list[dict]:
        """Extract ERROR test cases from pytest output."""
        errors = []
        error_pattern = r"ERROR ([\w/\._-]+)::(\w+)"
        matches = re.findall(error_pattern, output)

        for file_path, test_name in matches:
            error_section = self._extract_error_section(output, file_path, test_name)
            errors.append(
                {
                    "file": file_path,
                    "test": test_name,
                    "traceback": error_section,
                }
            )

        return errors

    def _extract_failure_section(
        self, output: str, file_path: str, test_name: str
    ) -> str:
        """Extract the detailed failure section for a specific test."""
        pattern = rf"_{{{test_name}}}.*?(?=_{{|\Z)"
        match = re.search(pattern, output, re.DOTALL)
        if match:
            return match.group(0)
        return ""

    def _extract_error_section(
        self, output: str, file_path: str, test_name: str
    ) -> str:
        """Extract the detailed error section for a specific test."""
        return self._extract_failure_section(output, file_path, test_name)

    def _extract_summary(self, output: str) -> dict:
        """Extract test summary statistics."""
        summary = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
        }

        summary_pattern = r"=+ (?:(\d+) failed)?(?:, )?(?:(\d+) passed)?(?:, )?(?:(\d+) error)?(?:, )?(?:(\d+) skipped)?"
        match = re.search(summary_pattern, output)

        if match:
            if match.group(1):
                summary["failed"] = int(match.group(1))
            if match.group(2):
                summary["passed"] = int(match.group(2))
            if match.group(3):
                summary["errors"] = int(match.group(3))
            if match.group(4):
                summary["skipped"] = int(match.group(4))

        return summary

    def _analyze_failure(self, failure: dict, app_path: str | None) -> dict:
        """Analyze a single test failure and suggest fixes."""
        traceback = failure["traceback"]
        file_path = failure["file"]
        test_name = failure["test"]

        category = self._categorize_failure(traceback, file_path)
        suggested_fix = self._suggest_fix(traceback, file_path, category)

        return {
            "file": file_path,
            "test": test_name,
            "category": category,
            "is_sdk_bug": category in ["sdk_bug", "sdk_missing_feature"],
            "is_app_bug": category in ["app_bug", "assertion_error", "import_error"],
            "suggested_fix": suggested_fix,
            "traceback": traceback[:500],
        }

    def _analyze_error(self, error: dict, app_path: str | None) -> dict:
        """Analyze a single test error and suggest fixes."""
        return self._analyze_failure(error, app_path)

    def _categorize_failure(self, traceback: str, file_path: str) -> str:
        """Categorize the type of failure."""
        if "AssertionError" in traceback:
            return "assertion_error"
        elif "ImportError" in traceback or "ModuleNotFoundError" in traceback:
            return "import_error"
        elif "AttributeError" in traceback:
            return "attribute_error"
        elif "TypeError" in traceback:
            return "type_error"
        elif "ValueError" in traceback:
            return "value_error"
        elif "KeyError" in traceback:
            return "key_error"
        elif "FileNotFoundError" in traceback:
            return "file_not_found"
        elif "fixture" in traceback.lower():
            return "fixture_error"
        elif "soar_sdk" in traceback or "phantom" in traceback:
            return "sdk_bug"
        else:
            return "unknown"

    def _suggest_fix(self, traceback: str, file_path: str, category: str) -> dict:
        """Suggest a fix based on the failure category."""
        if category == "assertion_error":
            return self._suggest_assertion_fix(traceback)
        elif category == "import_error":
            return self._suggest_import_fix(traceback)
        elif category == "attribute_error":
            return self._suggest_attribute_fix(traceback)
        elif category == "type_error":
            return self._suggest_type_fix(traceback)
        elif category == "fixture_error":
            return self._suggest_fixture_fix(traceback)
        else:
            return {
                "type": "manual_review",
                "description": "Manual review required for this failure",
            }

    def _suggest_assertion_fix(self, traceback: str) -> dict:
        """Suggest fix for assertion errors."""
        assert_line = self._extract_assert_line(traceback)
        return {
            "type": "assertion",
            "description": "Assertion failed - review test expectations",
            "assert_line": assert_line,
            "action": "Review the assertion and update test expectations or fix the code being tested",
        }

    def _suggest_import_fix(self, traceback: str) -> dict:
        """Suggest fix for import errors."""
        missing_module = self._extract_missing_module(traceback)
        return {
            "type": "import",
            "description": f"Missing module: {missing_module}",
            "action": f"Add '{missing_module}' to dependencies in pyproject.toml",
            "command": f"uv add {missing_module}",
        }

    def _suggest_attribute_fix(self, traceback: str) -> dict:
        """Suggest fix for attribute errors."""
        return {
            "type": "attribute",
            "description": "Attribute not found",
            "action": "Check if the attribute exists or if there's a typo",
        }

    def _suggest_type_fix(self, traceback: str) -> dict:
        """Suggest fix for type errors."""
        return {
            "type": "type",
            "description": "Type mismatch",
            "action": "Review the types being passed to the function",
        }

    def _suggest_fixture_fix(self, traceback: str) -> dict:
        """Suggest fix for pytest fixture errors."""
        fixture_name = self._extract_fixture_name(traceback)
        return {
            "type": "fixture",
            "description": f"Fixture '{fixture_name}' not found or misconfigured",
            "action": "Check conftest.py or add the missing fixture",
        }

    def _extract_assert_line(self, traceback: str) -> str:
        """Extract the assertion line from traceback."""
        assert_pattern = r"assert (.+)"
        match = re.search(assert_pattern, traceback)
        return match.group(1) if match else ""

    def _extract_missing_module(self, traceback: str) -> str:
        """Extract the missing module name from import error."""
        module_pattern = r"No module named ['\"](\w+)['\"]"
        match = re.search(module_pattern, traceback)
        return match.group(1) if match else "unknown"

    def _extract_fixture_name(self, traceback: str) -> str:
        """Extract the fixture name from fixture error."""
        fixture_pattern = r"fixture ['\"](\w+)['\"]"
        match = re.search(fixture_pattern, traceback)
        return match.group(1) if match else "unknown"
