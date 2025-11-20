# SOAR Test Assistant MCP Server

Model Context Protocol server for automated test analysis and fixing in Splunk SOAR SDK development.

## Overview

This MCP server provides AI-powered test automation for Claude Code (or any MCP-compatible AI agent), enabling:

- Automatic detection and fixing of import errors
- Intelligent analysis of test failures
- Proposed fixes for assertions, type errors, and attribute errors
- Iterative test execution until passing

## Installation

### Quick Start

```bash
cd mcp_server
./install.sh
```

Restart Claude Code (or your MCP client) after installation.

### Manual Configuration

Add to your MCP settings file:
- macOS/Linux: `~/.config/claude-code/mcp_settings.json`
- Windows: `%APPDATA%\claude-code\mcp_settings.json`

```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/mcp_server",
        "soar_test_assistant"
      ]
    }
  }
}
```

## Usage

The MCP server works from any directory. Open Claude Code (or your MCP client) in your project and use natural language:

### From App Directory

```bash
cd /path/to/your-soar-app
code .
```

Examples:
- "Run and fix tests for ."
- "Fix my app tests"
- "Run and fix tests in tests/test_actions.py"

### From SDK Directory

```bash
cd /path/to/splunk-soar-sdk
code .
```

Examples:
- "Run and fix SDK unit tests"
- "Run and fix tests for tests/example_app"
- "Run SDK integration tests"

Note: Integration tests require SOAR instance credentials (IP, username, password). Claude Code (or your MCP client) will prompt for these if not provided.

### From Any Directory

```bash
cd ~/projects
code .
```

Example:
- "Run and fix tests for /path/to/my-app"

## MCP Tools

### run_and_fix_tests

Main tool that runs tests, analyzes failures, applies fixes, and re-runs until passing or max iterations reached.

Parameters:
- `path` (required): Path to test location
- `test_type` (optional): "app", "sdk_unit", or "sdk_integration" (auto-detected)
- `test_path` (optional): Specific test file or directory
- `soar_instance` (optional): For integration tests: `{"ip": "...", "username": "...", "password": "..."}`
- `max_iterations` (optional): Maximum fix attempts (default: 5)
- `verbose` (optional): Enable detailed output (default: false)

Returns:
- Test status
- Applied fixes
- Proposed fixes pending approval (if any)
- Test output

### analyze_test_failure

Analyzes pytest output to identify failures and classify issues.

Parameters:
- `test_output` (required): Full pytest output
- `app_path` (optional): Path to app being tested

Returns:
- Detailed failure analysis
- Classification (SDK bug vs app bug)
- Suggested fixes

### fix_test_failure

Applies automated fixes based on analysis.

Parameters:
- `failure_analysis` (required): JSON from analyze_test_failure
- `app_path` (required): Path to app
- `auto_apply` (optional): Auto-apply fixes (default: true)

Returns:
- Modified files
- Applied changes

### apply_approved_fixes

Applies fixes after user review and approval.

Parameters:
- `app_path` (required): Path to app
- `approved_fixes` (required): List of approved fixes from pending_fixes

Returns:
- Modified files
- Applied fixes
- Errors (if any)

## How It Works

### Test Execution Flow

1. Run tests with appropriate command
2. Parse pytest output to identify failures
3. Classify errors (import, assertion, type, attribute)
4. Determine if SDK bug or app bug
5. Apply automatic fixes or propose changes
6. Re-run tests
7. Repeat until passing or max iterations

### Automatic Fixes

Import errors are fixed automatically:
- Missing packages: `uv add <package>`
- ModuleNotFoundError: Install missing dependencies

No user approval required.

### Proposed Fixes

Complex issues require user approval:

**Assertion errors**: Analyzes expected vs actual values, proposes swapping comparisons or adding review comments.

**Type errors**: Detects type mismatches (int/str), proposes conversions.

**Attribute errors**: Identifies None access issues, proposes protective checks.

Example proposed fix:
```
File: tests/test_api.py
Old: assert response.status_code == 200
New: assert response.status_code == 404
Reasoning: Actual value is 404, not 200. Test expectation may need updating.
Safety note: Changes test expectations
```

### Credential Handling

Integration tests require SOAR instance credentials. If not provided:

1. MCP server returns credentials_required status
2. Claude Code (or your MCP client) prompts for IP, username, password
3. User provides credentials
4. Tests run with provided credentials

Credentials can also be provided upfront in the initial request.

## Configuration

The `[tool.uv.sources]` section in pyproject.toml enables local SDK development:

```toml
[tool.uv.sources]
splunk-soar-sdk = { path = "..", editable = true }
```

This allows the MCP server to use your local SDK installation. Remove this section if publishing to PyPI.

## Development

### Project Structure

```
mcp_server/
├── src/soar_test_assistant/
│   ├── __init__.py
│   ├── server.py          # MCP server and tools
│   ├── test_analyzer.py   # Failure analysis
│   └── test_fixer.py      # Fix application
├── tests/                  # Unit tests
├── pyproject.toml
├── LICENSE
└── README.md
```

### Running Tests

```bash
uv run pytest
```

### Code Quality

```bash
uv run ruff check src/
uv run ruff format src/
```

## Repository Location

The MCP server is bundled with the Splunk SOAR SDK. This provides:
- Tight integration with SDK development
- Version alignment
- Unified CI/CD and issue tracking
- Natural discoverability for SDK users

If significant independent usage develops, the server can be split into its own repository.

## Support

Report issues at https://github.com/phantomcyber/splunk-soar-sdk/issues

## License

Apache License 2.0

Copyright (c) 2024 Splunk Inc.

See LICENSE file for full terms.
