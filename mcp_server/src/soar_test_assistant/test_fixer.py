import subprocess
from pathlib import Path


class TestFixer:
    def __init__(self, app_path: Path):
        self.app_path = app_path

    async def apply_fixes(self, analysis: dict, auto_apply: bool = True) -> dict:
        """Apply fixes based on failure analysis."""
        if not auto_apply:
            return {
                "status": "dry_run",
                "fixes_available": self._count_fixable_issues(analysis),
                "message": "Auto-apply is disabled. No changes made.",
            }

        files_modified = []
        fixes_applied = []

        for failure in analysis.get("failures", []):
            if failure.get("suggested_fix"):
                result = await self._apply_fix(failure)
                if result["applied"]:
                    fixes_applied.append(result)
                    if result.get("file_modified"):
                        files_modified.append(result["file_modified"])

        for error in analysis.get("errors", []):
            if error.get("suggested_fix"):
                result = await self._apply_fix(error)
                if result["applied"]:
                    fixes_applied.append(result)
                    if result.get("file_modified"):
                        files_modified.append(result["file_modified"])

        return {
            "status": "completed",
            "files_modified": list(set(files_modified)),
            "fixes_applied": fixes_applied,
            "total_fixes": len(fixes_applied),
        }

    async def _apply_fix(self, failure: dict) -> dict:
        """Apply a single fix based on failure analysis."""
        suggested_fix = failure["suggested_fix"]
        fix_type = suggested_fix.get("type")

        if fix_type == "import":
            return await self._fix_import_error(failure, suggested_fix)
        elif fix_type == "assertion":
            return await self._fix_assertion_error(failure, suggested_fix)
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
            result = subprocess.run(
                command.split(),
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
                "reason": f"Error installing dependency: {str(e)}",
            }

    async def _fix_assertion_error(self, failure: dict, suggested_fix: dict) -> dict:
        """Fix assertion errors by analyzing and updating test expectations."""
        return {
            "applied": False,
            "reason": "Assertion errors require manual review and cannot be automatically fixed",
            "suggestion": suggested_fix.get("action"),
        }

    async def _fix_fixture_error(self, failure: dict, suggested_fix: dict) -> dict:
        """Fix fixture errors by creating missing fixtures."""
        return {
            "applied": False,
            "reason": "Fixture errors require manual fixture creation",
            "suggestion": suggested_fix.get("action"),
        }

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
