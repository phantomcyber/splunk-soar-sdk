#!/usr/bin/env python3
"""Generate integration test summary from JUnit XML reports."""

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    """Test result summary for a single version."""

    version: str
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    failures: list[dict[str, str]]


def parse_junit_xml(xml_path: Path) -> TestResult:
    """Parse JUnit XML file and extract test results."""
    tree = ET.parse(xml_path)  # noqa: S314
    root = tree.getroot()

    version = xml_path.stem.replace("junit-", "")
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    duration = 0.0
    failures = []

    for testsuite in root.findall(".//testsuite"):
        duration += float(testsuite.get("time", 0))
        passed += (
            int(testsuite.get("tests", 0))
            - int(testsuite.get("failures", 0))
            - int(testsuite.get("skipped", 0))
            - int(testsuite.get("errors", 0))
        )
        failed += int(testsuite.get("failures", 0))
        skipped += int(testsuite.get("skipped", 0))
        errors += int(testsuite.get("errors", 0))

    for testcase in root.findall(".//testcase"):
        failure = testcase.find("failure")
        error = testcase.find("error")

        if failure is not None:
            failures.append(
                {
                    "name": f"{testcase.get('classname')}.{testcase.get('name')}",
                    "message": failure.get("message", "No message"),
                    "type": failure.get("type", "AssertionError"),
                    "output": (failure.text or "")[:500],
                }
            )
        elif error is not None:
            failures.append(
                {
                    "name": f"{testcase.get('classname')}.{testcase.get('name')}",
                    "message": error.get("message", "No message"),
                    "type": error.get("type", "Error"),
                    "output": (error.text or "")[:500],
                }
            )

    return TestResult(
        version=version,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        duration=duration,
        failures=failures,
    )


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def generate_markdown_summary(
    results: list[TestResult], run_url: str | None = None
) -> str:
    """Generate markdown summary from test results."""
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_errors = sum(r.errors for r in results)

    md = "# Integration Test Results\n"

    if total_failed + total_errors == 0:
        md += f"## ✅ {total_passed} tests passed!\n"
    else:
        md += "## ⚠️ Some tests failed.\n"

    md += "| Version | ✅ Passed | ❌ Failed | ⏭️ Skipped | Duration |\n"
    md += "| ------- | --------- | --------- | ---------- | -------- |\n"

    for result in sorted(results, key=lambda r: r.version):
        md += f"| {result.version} | {result.passed} | {result.failed + result.errors} | {result.skipped} | {format_duration(result.duration)} |\n"

    has_failures = any(r.failures for r in results)
    if has_failures:
        md += "## Failed Tests\n"
        md += "| Version | Name | Message | Type |\n"
        md += "| ------- | ---- | ------- | ---- |\n"
        for result in results:
            if result.failures:
                for failure in result.failures:
                    message = failure["message"]
                    if len(message) > 200:
                        message = message[:200].strip() + "…"
                    md += f"| {result.version} | {failure['name']} | {message} | {failure['type']} |\n"

    if run_url:
        md += "---\n[View full logs and artifacts](" + run_url + ")\n"

    return md


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: generate_test_summary.py <test-results-dir> [output-file] [run-url]"
        )
        return 1

    test_results_dir = Path(sys.argv[1])
    if not test_results_dir.exists():
        print(f"Error: Directory {test_results_dir} does not exist")
        return 1

    junit_files = list(test_results_dir.glob("**/junit-*.xml"))
    if not junit_files:
        print(f"Error: No JUnit XML files found in {test_results_dir}")
        return 1

    results = []
    for junit_file in junit_files:
        try:
            result = parse_junit_xml(junit_file)
            results.append(result)
        except Exception as e:
            print(f"Error parsing {junit_file}: {e}")
            continue

    if not results:
        print("Error: No test results could be parsed")
        return 1

    run_url = sys.argv[3] if len(sys.argv) > 3 else None
    summary = generate_markdown_summary(results, run_url)
    print(summary)

    summary_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("test-summary.md")
    summary_file.write_text(summary)
    print(f"\nSummary written to {summary_file}", file=sys.stderr)

    has_failures = any(r.failed + r.errors > 0 for r in results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
