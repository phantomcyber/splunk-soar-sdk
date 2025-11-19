"""MCP server for SOAR SDK test analysis and auto-fixing."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .test_analyzer import TestAnalyzer
from .test_fixer import TestFixer

app = Server("soar-test-assistant")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_test_failure",
            description=(
                "Analyzes pytest test output to identify failures and determine if they are "
                "SDK bugs or app bugs. Returns detailed analysis and suggested fixes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_output": {
                        "type": "string",
                        "description": "The full pytest output from a test run",
                    },
                    "app_path": {
                        "type": "string",
                        "description": "Path to the app being tested (optional)",
                    },
                },
                "required": ["test_output"],
            },
        ),
        Tool(
            name="fix_test_failure",
            description=(
                "Applies fixes for identified test failures. Takes analysis from "
                "analyze_test_failure and applies the suggested fixes to the codebase."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "failure_analysis": {
                        "type": "string",
                        "description": "JSON output from analyze_test_failure",
                    },
                    "app_path": {
                        "type": "string",
                        "description": "Path to the app to fix",
                    },
                    "auto_apply": {
                        "type": "boolean",
                        "description": "Whether to automatically apply fixes",
                        "default": True,
                    },
                },
                "required": ["failure_analysis", "app_path"],
            },
        ),
        Tool(
            name="run_and_fix_tests",
            description=(
                "Automatically runs tests, analyzes failures, applies fixes, and re-runs "
                "until all tests pass or maximum iterations reached. Works for app tests, "
                "SDK unit tests, and SDK integration tests. Auto-detects test type or can "
                "be specified explicitly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Path to test location. For apps: path to app dir. "
                            "For SDK: path to SDK root (usually '.' or absolute path)"
                        ),
                    },
                    "test_type": {
                        "type": "string",
                        "description": (
                            "Type of tests to run. Auto-detected if not specified. "
                            "Options: 'app', 'sdk_unit', 'sdk_integration'"
                        ),
                        "enum": ["app", "sdk_unit", "sdk_integration"],
                    },
                    "test_path": {
                        "type": "string",
                        "description": "Specific test file or directory (optional)",
                    },
                    "soar_instance": {
                        "type": "object",
                        "description": (
                            "Required for sdk_integration tests. "
                            'Format: {"ip": "10.1.19.88", "username": "admin", "password": "pass"}'
                        ),
                        "properties": {
                            "ip": {"type": "string"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum number of fix attempts",
                        "default": 5,
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Enable verbose output",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "analyze_test_failure":
        return await analyze_test_failure(arguments)
    elif name == "fix_test_failure":
        return await fix_test_failure(arguments)
    elif name == "run_and_fix_tests":
        return await run_and_fix_tests(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def analyze_test_failure(arguments: dict) -> list[TextContent]:
    test_output = arguments["test_output"]
    app_path = arguments.get("app_path")

    analyzer = TestAnalyzer()
    analysis = analyzer.analyze(test_output, app_path)

    return [
        TextContent(
            type="text",
            text=json.dumps(analysis, indent=2),
        )
    ]


async def fix_test_failure(arguments: dict) -> list[TextContent]:
    failure_analysis_str = arguments["failure_analysis"]
    app_path = Path(arguments["app_path"])
    auto_apply = arguments.get("auto_apply", True)

    try:
        failure_analysis = json.loads(failure_analysis_str)
    except json.JSONDecodeError as e:
        return [
            TextContent(
                type="text",
                text=f"Error parsing failure analysis: {e}",
            )
        ]

    fixer = TestFixer(app_path)
    result = await fixer.apply_fixes(failure_analysis, auto_apply=auto_apply)

    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2),
        )
    ]


async def run_and_fix_tests(arguments: dict) -> list[TextContent]:
    test_path_arg = Path(arguments["path"])
    test_type = arguments.get("test_type")
    specific_test = arguments.get("test_path")
    soar_instance = arguments.get("soar_instance")
    max_iterations = arguments.get("max_iterations", 5)
    verbose = arguments.get("verbose", False)

    if not test_path_arg.exists():
        return [
            TextContent(
                type="text",
                text=f"Error: Path does not exist: {test_path_arg}",
            )
        ]

    # Detect test type if not specified
    if test_type is None:
        test_type = detect_test_type(test_path_arg)

    analyzer = TestAnalyzer()
    fixer = TestFixer(test_path_arg)
    iteration = 0
    all_fixes: list[dict] = []
    test_history = []

    if verbose:
        test_type_display = {
            "app": "App Tests",
            "sdk_unit": "SDK Unit Tests",
            "sdk_integration": "SDK Integration Tests",
        }.get(test_type, test_type)

    while iteration < max_iterations:
        iteration += 1

        if verbose:
            output = f"\n{'=' * 60}\n"
            output += f"Test Type: {test_type_display}\n"
            output += f"Iteration {iteration}/{max_iterations}\n"
            output += f"{'=' * 60}\n"
        else:
            output = f"[{test_type}] Iteration {iteration}/{max_iterations}... "

        test_result = await run_tests(
            test_path_arg,
            test_path=specific_test,
            test_type=test_type,
            soar_instance=soar_instance,
        )
        test_history.append(
            {
                "iteration": iteration,
                "exit_code": test_result["exit_code"],
                "output": test_result["output"]
                if verbose
                else test_result["output"][-500:],
            }
        )

        if test_result["exit_code"] == 0:
            summary = {
                "status": "success",
                "iterations": iteration,
                "fixes_applied": all_fixes,
                "final_output": test_result["output"]
                if verbose
                else "All tests passed!",
            }
            return [
                TextContent(
                    type="text",
                    text=output
                    + "\n[PASS] All tests passed!\n\n"
                    + json.dumps(summary, indent=2),
                )
            ]

        analysis = analyzer.analyze(test_result["output"], str(test_path_arg))

        if not analysis.get("failures"):
            summary = {
                "status": "no_failures_detected",
                "iterations": iteration,
                "exit_code": test_result["exit_code"],
                "fixes_applied": all_fixes,
                "final_output": test_result["output"][-1000:],
            }
            return [
                TextContent(
                    type="text",
                    text=(
                        output
                        + "\n[FAIL] Tests failed but no specific failures detected.\n\n"
                        + json.dumps(summary, indent=2)
                    ),
                )
            ]

        fix_result = await fixer.apply_fixes(analysis, auto_apply=True)
        all_fixes.append(
            {
                "iteration": iteration,
                "fixes": fix_result,
            }
        )

        if not fix_result.get("files_modified"):
            summary = {
                "status": "no_fixes_available",
                "iterations": iteration,
                "fixes_applied": all_fixes,
                "analysis": analysis,
                "final_output": test_result["output"][-1000:],
            }
            return [
                TextContent(
                    type="text",
                    text=(
                        output
                        + "\n[FAIL] No fixes available for current failures.\n\n"
                        + json.dumps(summary, indent=2)
                    ),
                )
            ]

        if verbose:
            output += f"Applied {len(fix_result['files_modified'])} fixes\n"

    summary = {
        "status": "max_iterations_reached",
        "iterations": iteration,
        "fixes_applied": all_fixes,
        "test_history": test_history,
    }

    return [
        TextContent(
            type="text",
            text=(
                f"\n[FAIL] Max iterations ({max_iterations}) reached without passing all tests.\n\n"
                + json.dumps(summary, indent=2)
            ),
        )
    ]


def detect_test_type(path: Path) -> str:
    """Detect what type of tests we're running.

    Returns:
        - "sdk_unit": SDK unit tests
        - "sdk_integration": SDK integration tests
        - "app": App tests
    """
    # Check if it's the SDK root (has src/soar_sdk)
    if (path / "src" / "soar_sdk").exists():
        # It's the SDK - check which type of test
        if (path / "tests" / "integration").exists():
            # Default to integration if the path suggests it
            return "sdk_integration"
        return "sdk_unit"

    # Check if it's an app (has pyproject.toml with [tool.soar.app])
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject) as f:
                content = f.read()
                if "[tool.soar.app]" in content:
                    return "app"
        except OSError:
            pass

    # Default to app if unsure
    return "app"


async def run_tests(
    app_path: Path,
    test_path: str | None = None,
    test_type: str | None = None,
    soar_instance: dict | None = None,
) -> dict:
    """Run tests based on detected or specified type.

    Args:
        app_path: Path to test location
        test_path: Specific test file/directory (optional)
        test_type: Override test type detection (optional)
        soar_instance: For integration tests: {"ip": "10.1.19.88", "username": "admin", "password": "pass"}
    """
    if test_type is None:
        test_type = detect_test_type(app_path)

    env = None
    cwd = app_path

    if test_type == "sdk_unit":
        # Run SDK unit tests
        cmd = ["uv", "run", "soarapps", "test", "unit"]
        if test_path:
            cmd.extend(["-t", test_path])
        cwd = app_path

    elif test_type == "sdk_integration":
        # Run SDK integration tests (needs SOAR instance)
        if not soar_instance:
            return {
                "exit_code": 1,
                "output": (
                    "Error: Integration tests require SOAR instance credentials.\n\n"
                    "Please provide the soar_instance parameter with:\n"
                    '  {"ip": "10.1.19.88", "username": "admin", "password": "yourpassword"}\n\n'
                    "Example usage:\n"
                    "  soar_instance={'ip': '10.1.19.88', 'username': 'admin', 'password': 'password'}"
                ),
            }

        cmd = ["uv", "run", "soarapps", "test", "integration", soar_instance["ip"]]
        if test_path:
            cmd.extend(["-t", test_path])

        # Set environment variables for authentication
        import os

        env = {
            **os.environ,
            "PHANTOM_USERNAME": soar_instance.get("username", "admin"),
            "PHANTOM_PASSWORD": soar_instance.get("password", "password"),
        }
        cwd = app_path

    elif test_type == "app":
        # Run app tests
        cmd = ["uv", "run", "soarapps", "app", "test", str(app_path)]
        if test_path:
            cmd.extend(["-t", test_path])
        cwd = app_path.parent

    else:
        return {
            "exit_code": 1,
            "output": f"Error: Unknown test type: {test_type}",
        }

    result = subprocess.run(  # noqa: S603
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )

    return {
        "exit_code": result.returncode,
        "output": result.stdout + result.stderr,
        "test_type": test_type,
    }


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def cli() -> None:
    """CLI entry point for the MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
