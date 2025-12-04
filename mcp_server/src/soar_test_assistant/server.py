import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("soar-test-assistant")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_tests",
            description=(
                "Runs SDK unit or integration tests and returns the full output. "
                "The AI agent analyzes this output to determine what fixes are needed. "
                "Use this first to see what's failing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "description": "Type of SDK tests",
                        "enum": ["unit", "integration"],
                        "default": "unit",
                    },
                    "test_path": {
                        "type": "string",
                        "description": "Specific test file or directory (optional)",
                    },
                    "soar_instance": {
                        "type": "object",
                        "description": "Required for integration tests",
                        "properties": {
                            "ip": {"type": "string"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                },
            },
        ),
        Tool(
            name="fix_and_run_tests",
            description=(
                "Applies AI-proposed changes (file edits or commands) and re-runs tests. "
                "After analyzing test failures, the AI determines what changes are needed, "
                "then calls this tool to apply those changes and verify tests pass. "
                "Can be called multiple times until all tests pass."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "description": "Type of SDK tests",
                        "enum": ["unit", "integration"],
                        "default": "unit",
                    },
                    "test_path": {
                        "type": "string",
                        "description": "Specific test file or directory (optional)",
                    },
                    "soar_instance": {
                        "type": "object",
                        "description": "Required for integration tests",
                        "properties": {
                            "ip": {"type": "string"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                    "changes": {
                        "type": "array",
                        "description": "List of changes to apply before running tests",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["edit_file", "run_command"],
                                    "description": "Type of change",
                                },
                                "file": {
                                    "type": "string",
                                    "description": "For edit_file: relative path to file from SDK root",
                                },
                                "old_content": {
                                    "type": "string",
                                    "description": "For edit_file: exact content to replace",
                                },
                                "new_content": {
                                    "type": "string",
                                    "description": "For edit_file: replacement content",
                                },
                                "command": {
                                    "type": "string",
                                    "description": "For run_command: bash command to execute",
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Why this change fixes the issue",
                                },
                            },
                            "required": ["type", "reasoning"],
                        },
                    },
                },
                "required": ["changes"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "analyze_tests":
        return await analyze_tests(arguments)
    elif name == "fix_and_run_tests":
        return await fix_and_run_tests(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def analyze_tests(arguments: dict) -> list[TextContent]:
    test_type = arguments.get("test_type", "unit")
    test_path = arguments.get("test_path")
    soar_instance = arguments.get("soar_instance")

    sdk_root = find_sdk_root()
    result = await run_sdk_tests(sdk_root, test_type, test_path, soar_instance)

    if result["exit_code"] == 0:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "All tests passed!",
                        "output": result["output"],
                    },
                    indent=2,
                ),
            )
        ]

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "failed",
                    "exit_code": result["exit_code"],
                    "test_output": result["output"],
                    "message": "Tests failed. Analyze the output and call fix_and_run_tests with the changes.",
                },
                indent=2,
            ),
        )
    ]


async def fix_and_run_tests(arguments: dict) -> list[TextContent]:
    test_type = arguments.get("test_type", "unit")
    test_path = arguments.get("test_path")
    soar_instance = arguments.get("soar_instance")
    changes = arguments.get("changes", [])

    sdk_root = find_sdk_root()
    applied_changes = []
    errors = []

    for change in changes:
        change_type = change.get("type")
        reasoning = change.get("reasoning", "No reasoning provided")

        try:
            if change_type == "edit_file":
                file_path = sdk_root / change["file"]
                old_content = change["old_content"]
                new_content = change["new_content"]

                if not file_path.exists():
                    errors.append(f"File not found: {file_path}")
                    continue

                content = file_path.read_text()
                if old_content not in content:
                    errors.append(
                        f"old_content not found in {change['file']}. "
                        f"File may have changed or content doesn't match exactly."
                    )
                    continue

                new_file_content = content.replace(old_content, new_content, 1)
                file_path.write_text(new_file_content)

                applied_changes.append(
                    {
                        "type": "edit_file",
                        "file": change["file"],
                        "reasoning": reasoning,
                    }
                )

            elif change_type == "run_command":
                command = change["command"]
                result = subprocess.run(  # noqa: S603
                    ["bash", "-c", command],  # noqa: S607
                    cwd=sdk_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )

                if result.returncode != 0:
                    errors.append(f"Command failed: {command}\nError: {result.stderr}")
                    continue

                applied_changes.append(
                    {
                        "type": "run_command",
                        "command": command,
                        "reasoning": reasoning,
                        "output": result.stdout[:200],
                    }
                )

            else:
                errors.append(f"Unknown change type: {change_type}")

        except Exception as e:
            errors.append(f"Error applying change: {e!s}")

    if errors and not applied_changes:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": "Failed to apply changes",
                        "errors": errors,
                    },
                    indent=2,
                ),
            )
        ]

    test_result = await run_sdk_tests(sdk_root, test_type, test_path, soar_instance)

    if test_result["exit_code"] == 0:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "All tests passed!",
                        "applied_changes": applied_changes,
                        "test_output": test_result["output"][-1000:],
                    },
                    indent=2,
                ),
            )
        ]

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "still_failing",
                    "message": "Changes applied but tests still failing. Analyze output and try again.",
                    "applied_changes": applied_changes,
                    "errors": errors if errors else None,
                    "test_output": test_result["output"],
                },
                indent=2,
            ),
        )
    ]


async def run_sdk_tests(
    sdk_root: Path,
    test_type: str,
    test_path: str | None = None,
    soar_instance: dict | None = None,
) -> dict:
    env = os.environ.copy()

    if test_type == "unit":
        cmd = ["uv", "run", "python", "-m", "pytest"]
        if test_path:
            cmd.append(test_path)
        else:
            cmd.append("tests/")
        cmd.extend(["-m", "not integration", "--tb=long", "-v"])

    elif test_type == "integration":
        if not soar_instance:
            return {
                "exit_code": 1,
                "output": (
                    "ERROR: Integration tests require SOAR instance credentials.\n"
                    'Provide soar_instance: {"ip": "10.1.19.88", "username": "admin", "password": "pass"}'
                ),
            }

        cmd = ["uv", "run", "python", "-m", "pytest"]
        if test_path:
            cmd.append(test_path)
        else:
            cmd.append("tests/integration/")
        cmd.extend(["-m", "integration", "--tb=short", "-v", "--reruns=2"])

        env.update(
            {
                "PHANTOM_URL": f"https://{soar_instance['ip']}",
                "PHANTOM_USERNAME": soar_instance.get("username", "admin"),
                "PHANTOM_PASSWORD": soar_instance.get("password", "password"),
            }
        )

    else:
        return {"exit_code": 1, "output": f"Unknown test type: {test_type}"}

    result = subprocess.run(  # noqa: S603
        cmd,
        cwd=sdk_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "exit_code": result.returncode,
        "output": result.stdout + result.stderr,
    }


def find_sdk_root() -> Path:
    current = Path.cwd()
    while current != current.parent:
        if (current / "src" / "soar_sdk").exists():
            return current
        current = current.parent
    return Path.cwd()


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
