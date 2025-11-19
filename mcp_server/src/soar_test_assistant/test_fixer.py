"""Automated test failure fixer that applies fixes based on analysis."""

import re
import subprocess
from pathlib import Path


class TestFixer:
    def __init__(self, app_path: Path) -> None:
        self.app_path = app_path

    async def apply_fixes(
        self, analysis: dict, auto_apply: bool = True, approval_callback=None
    ) -> dict:
        """Apply fixes based on failure analysis."""
        if not auto_apply:
            return {
                "status": "dry_run",
                "fixes_available": self._count_fixable_issues(analysis),
                "message": "Auto-apply is disabled. No changes made.",
            }

        files_modified = []
        fixes_applied = []
        fixes_pending_approval = []

        for failure in analysis.get("failures", []):
            if failure.get("suggested_fix"):
                result = await self._apply_fix(failure, approval_callback)
                if result["applied"]:
                    fixes_applied.append(result)
                    if result.get("file_modified"):
                        files_modified.append(result["file_modified"])
                elif result.get("requires_approval"):
                    fixes_pending_approval.append(result)

        for error in analysis.get("errors", []):
            if error.get("suggested_fix"):
                result = await self._apply_fix(error, approval_callback)
                if result["applied"]:
                    fixes_applied.append(result)
                    if result.get("file_modified"):
                        files_modified.append(result["file_modified"])
                elif result.get("requires_approval"):
                    fixes_pending_approval.append(result)

        return {
            "status": "completed",
            "files_modified": list(set(files_modified)),
            "fixes_applied": fixes_applied,
            "fixes_pending_approval": fixes_pending_approval,
            "total_fixes": len(fixes_applied),
            "total_pending": len(fixes_pending_approval),
        }

    async def _apply_fix(self, failure: dict, approval_callback=None) -> dict:
        """Apply a single fix based on failure analysis."""
        suggested_fix = failure["suggested_fix"]
        fix_type = suggested_fix.get("type")

        if fix_type == "import":
            return await self._fix_import_error(failure, suggested_fix)
        elif fix_type == "assertion":
            return await self._fix_assertion_error(
                failure, suggested_fix, approval_callback
            )
        elif fix_type == "type":
            return await self._fix_type_error(failure, suggested_fix, approval_callback)
        elif fix_type == "attribute":
            return await self._fix_attribute_error(
                failure, suggested_fix, approval_callback
            )
        elif fix_type == "fixture":
            return await self._fix_fixture_error(failure, suggested_fix)
        else:
            return {
                "applied": False,
                "reason": f"No automated fix available for {fix_type}",
                "file": failure["file"],
                "test": failure["test"],
            }

    async def _fix_import_error(self, failure: dict, suggested_fix: dict) -> dict:
        """Fix import errors by installing missing packages."""
        command = suggested_fix.get("command")
        if not command:
            return {
                "applied": False,
                "reason": "No install command provided",
            }

        try:
            result = subprocess.run(  # noqa: S603
                command.split(),
                check=False,
                cwd=self.app_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return {
                    "applied": True,
                    "fix_type": "import",
                    "file": failure["file"],
                    "test": failure["test"],
                    "action": f"Installed missing dependency: {suggested_fix.get('description')}",
                    "file_modified": str(self.app_path / "pyproject.toml"),
                }
            else:
                return {
                    "applied": False,
                    "reason": f"Failed to install dependency: {result.stderr}",
                }
        except subprocess.TimeoutExpired:
            return {
                "applied": False,
                "reason": "Dependency installation timed out",
            }
        except Exception as e:
            return {
                "applied": False,
                "reason": f"Error installing dependency: {e!s}",
            }

    async def _fix_assertion_error(
        self, failure: dict, suggested_fix: dict, approval_callback=None
    ) -> dict:
        """Fix assertion errors by analyzing and proposing updates to test expectations."""
        test_file = self.app_path / failure["file"]

        if not test_file.exists():
            return {
                "applied": False,
                "reason": f"Test file not found: {test_file}",
            }

        try:
            test_content = test_file.read_text()
            traceback = failure.get("traceback", "")

            # Extract assertion details from traceback
            proposed_fix = self._propose_assertion_fix(test_content, traceback, failure)

            if not proposed_fix:
                return {
                    "applied": False,
                    "reason": "Could not generate a proposed fix for this assertion",
                    "suggestion": suggested_fix.get("action"),
                }

            # If we have an approval callback, present the fix for approval
            if approval_callback:
                approved = await approval_callback(proposed_fix)
                if approved:
                    # Apply the fix
                    new_content = test_content.replace(
                        proposed_fix["old_code"], proposed_fix["new_code"]
                    )
                    test_file.write_text(new_content)
                    return {
                        "applied": True,
                        "fix_type": "assertion",
                        "file": failure["file"],
                        "test": failure["test"],
                        "action": proposed_fix["reasoning"],
                        "file_modified": str(test_file),
                        "diff": proposed_fix,
                    }
                else:
                    return {
                        "applied": False,
                        "reason": "User declined the proposed fix",
                        "requires_approval": False,
                    }

            # No callback - return as pending approval
            return {
                "applied": False,
                "requires_approval": True,
                "proposed_fix": proposed_fix,
                "file": failure["file"],
                "test": failure["test"],
            }

        except Exception as e:
            return {
                "applied": False,
                "reason": f"Error proposing assertion fix: {e!s}",
            }

    async def _fix_type_error(
        self, failure: dict, suggested_fix: dict, approval_callback=None
    ) -> dict:
        """Fix type errors by analyzing and proposing type corrections."""
        test_file = self.app_path / failure["file"]

        if not test_file.exists():
            return {
                "applied": False,
                "reason": f"Test file not found: {test_file}",
            }

        try:
            test_content = test_file.read_text()
            traceback = failure.get("traceback", "")

            proposed_fix = self._propose_type_fix(test_content, traceback, failure)

            if not proposed_fix:
                return {
                    "applied": False,
                    "reason": "Could not generate a proposed fix for this type error",
                    "suggestion": suggested_fix.get("action"),
                }

            if approval_callback:
                approved = await approval_callback(proposed_fix)
                if approved:
                    new_content = test_content.replace(
                        proposed_fix["old_code"], proposed_fix["new_code"]
                    )
                    test_file.write_text(new_content)
                    return {
                        "applied": True,
                        "fix_type": "type",
                        "file": failure["file"],
                        "test": failure["test"],
                        "action": proposed_fix["reasoning"],
                        "file_modified": str(test_file),
                        "diff": proposed_fix,
                    }
                else:
                    return {
                        "applied": False,
                        "reason": "User declined the proposed fix",
                    }

            return {
                "applied": False,
                "requires_approval": True,
                "proposed_fix": proposed_fix,
                "file": failure["file"],
                "test": failure["test"],
            }

        except Exception as e:
            return {
                "applied": False,
                "reason": f"Error proposing type fix: {e!s}",
            }

    async def _fix_attribute_error(
        self, failure: dict, suggested_fix: dict, approval_callback=None
    ) -> dict:
        """Fix attribute errors by analyzing and proposing corrections."""
        test_file = self.app_path / failure["file"]

        if not test_file.exists():
            return {
                "applied": False,
                "reason": f"Test file not found: {test_file}",
            }

        try:
            test_content = test_file.read_text()
            traceback = failure.get("traceback", "")

            proposed_fix = self._propose_attribute_fix(test_content, traceback, failure)

            if not proposed_fix:
                return {
                    "applied": False,
                    "reason": "Could not generate a proposed fix for this attribute error",
                    "suggestion": suggested_fix.get("action"),
                }

            if approval_callback:
                approved = await approval_callback(proposed_fix)
                if approved:
                    new_content = test_content.replace(
                        proposed_fix["old_code"], proposed_fix["new_code"]
                    )
                    test_file.write_text(new_content)
                    return {
                        "applied": True,
                        "fix_type": "attribute",
                        "file": failure["file"],
                        "test": failure["test"],
                        "action": proposed_fix["reasoning"],
                        "file_modified": str(test_file),
                        "diff": proposed_fix,
                    }
                else:
                    return {
                        "applied": False,
                        "reason": "User declined the proposed fix",
                    }

            return {
                "applied": False,
                "requires_approval": True,
                "proposed_fix": proposed_fix,
                "file": failure["file"],
                "test": failure["test"],
            }

        except Exception as e:
            return {
                "applied": False,
                "reason": f"Error proposing attribute fix: {e!s}",
            }

    async def _fix_fixture_error(self, failure: dict, suggested_fix: dict) -> dict:
        """Fix fixture errors by creating missing fixtures."""
        return {
            "applied": False,
            "reason": "Fixture errors require manual fixture creation",
            "suggestion": suggested_fix.get("action"),
        }

    def _propose_assertion_fix(
        self, test_content: str, traceback: str, failure: dict
    ) -> dict | None:
        """Propose a fix for an assertion error."""
        # Extract the assertion from traceback
        assert_match = re.search(r"assert (.+)", traceback)
        if not assert_match:
            return None

        assert_line = assert_match.group(1).strip()

        # Try to extract expected vs actual values from traceback
        # Common patterns: "assert 200 == 404", "assert x == y", etc.
        comparison_match = re.search(
            r"assert\s+(.+?)\s*(==|!=|<|>|<=|>=)\s*(.+?)(?:\s|$)", traceback
        )

        if comparison_match:
            left = comparison_match.group(1).strip()
            operator = comparison_match.group(2)
            right = comparison_match.group(3).strip()

            # Look for assertion context in traceback
            # Format: "AssertionError: assert 200 == 404" or similar
            if "where" in traceback.lower() or "assert" in traceback.lower():
                # Try to find the assertion line in test content
                assert_pattern = re.escape(f"assert {assert_line}")
                if re.search(assert_pattern, test_content):
                    # Propose swapping expected/actual if it looks like wrong expectation
                    if operator == "==":
                        return {
                            "file": failure["file"],
                            "old_code": f"assert {left} == {right}",
                            "new_code": f"assert {right} == {left}",
                            "reasoning": (
                                f"Swapping comparison: actual value appears to be {right}, "
                                f"not {left}. This may indicate the test expectation needs updating."
                            ),
                            "safety_note": "Review carefully - this changes test expectations",
                        }

        # Fallback: suggest commenting out or reviewing the assertion
        return {
            "file": failure["file"],
            "old_code": f"assert {assert_line}",
            "new_code": f"# TODO: Review this assertion\n    assert {assert_line}",
            "reasoning": (
                "Assertion is failing. Adding TODO comment for manual review. "
                "The assertion logic may need to be updated based on actual behavior."
            ),
            "safety_note": "This doesn't fix the test, just marks it for review",
        }

    def _propose_type_fix(
        self, test_content: str, traceback: str, failure: dict
    ) -> dict | None:
        """Propose a fix for a type error."""
        # Extract type error details
        # Pattern: "expected str, got int" or "argument 1 must be str, not int"
        type_match = re.search(
            r"(?:expected|must be)\s+(\w+)(?:,|\s+not)\s+(?:got\s+)?(\w+)", traceback
        )

        if type_match:
            expected_type = type_match.group(1)
            actual_type = type_match.group(2)

            # Try to find the problematic line
            # Look for function calls with wrong type
            if "int" in actual_type and "str" in expected_type:
                # Look for numeric literals that should be strings
                number_pattern = r"(\w+)\((\d+)\)"
                matches = list(re.finditer(number_pattern, test_content))
                if matches:
                    first_match = matches[0]
                    return {
                        "file": failure["file"],
                        "old_code": first_match.group(0),
                        "new_code": f'{first_match.group(1)}("{first_match.group(2)}")',
                        "reasoning": (
                            f"Converting {actual_type} to {expected_type}. "
                            f"The function expects a string, but received an integer."
                        ),
                        "safety_note": "This converts a numeric argument to a string",
                    }

            elif "str" in actual_type and "int" in expected_type:
                # Look for string literals that should be integers
                string_pattern = r'(\w+)\(["\'](\d+)["\']\)'
                matches = list(re.finditer(string_pattern, test_content))
                if matches:
                    first_match = matches[0]
                    return {
                        "file": failure["file"],
                        "old_code": first_match.group(0),
                        "new_code": f"{first_match.group(1)}({first_match.group(2)})",
                        "reasoning": (
                            f"Converting {actual_type} to {expected_type}. "
                            f"The function expects an integer, but received a string."
                        ),
                        "safety_note": "This converts a string argument to an integer",
                    }

        return None

    def _propose_attribute_fix(
        self, test_content: str, traceback: str, failure: dict
    ) -> dict | None:
        """Propose a fix for an attribute error."""
        # Extract attribute error details
        # Pattern: "'NoneType' object has no attribute 'foo'"
        attr_match = re.search(r"has no attribute ['\"](\w+)['\"]", traceback)

        if attr_match:
            missing_attr = attr_match.group(1)

            # Check if this is a None check issue
            if "NoneType" in traceback:
                # Look for direct attribute access that should be protected
                attr_pattern = rf"(\w+)\.{missing_attr}"
                matches = list(re.finditer(attr_pattern, test_content))
                if matches:
                    first_match = matches[0]
                    var_name = first_match.group(1)
                    return {
                        "file": failure["file"],
                        "old_code": f"{var_name}.{missing_attr}",
                        "new_code": f"({var_name}.{missing_attr} if {var_name} else None)",
                        "reasoning": (
                            f"Adding None check for {var_name}. "
                            f"The object is None when accessing .{missing_attr}"
                        ),
                        "safety_note": "This adds a None check to prevent AttributeError",
                    }

        return None

    def _count_fixable_issues(self, analysis: dict) -> int:
        """Count how many issues can be automatically fixed."""
        count = 0
        fixable_types = ["import"]

        for failure in analysis.get("failures", []):
            fix = failure.get("suggested_fix", {})
            if fix.get("type") in fixable_types:
                count += 1

        for error in analysis.get("errors", []):
            fix = error.get("suggested_fix", {})
            if fix.get("type") in fixable_types:
                count += 1

        return count
