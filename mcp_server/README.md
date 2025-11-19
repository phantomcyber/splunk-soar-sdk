# SOAR SDK Test Assistant MCP Server

An MCP (Model Context Protocol) server that provides intelligent test analysis and auto-fix capabilities for Splunk SOAR SDK and apps.

## Features

- **Analyze Test Failures**: Parse pytest output and identify root causes
- **Fix Test Failures**: Automatically fix common test issues
- **Run and Fix**: Iteratively run tests, analyze failures, and apply fixes until passing
- **Multi-Test Support**: Works with app tests, SDK unit tests, AND SDK integration tests
- **Auto-Detection**: Automatically detects test type based on path

## Tools

### `analyze_test_failure`
Analyzes pytest output to determine if failures are due to SDK bugs or app bugs.

**Parameters:**
- `test_output`: The full pytest output
- `app_path`: Path to the app being tested (optional)

**Returns:**
- Analysis of test failures
- Classification (SDK bug vs app bug)
- Suggested fixes

### `fix_test_failure`
Applies fixes for identified test failures.

**Parameters:**
- `failure_analysis`: Output from `analyze_test_failure`
- `app_path`: Path to the app
- `auto_apply`: Whether to automatically apply fixes (default: true)

**Returns:**
- List of files modified
- Changes applied

### `run_and_fix_tests`
Iteratively runs tests and fixes failures until all tests pass or max iterations reached.

**Supports ALL test types:**
- **App tests**: Tests for apps built with the SDK
- **SDK unit tests**: SDK's own unit tests
- **SDK integration tests**: Tests against live SOAR instances

**Parameters:**
- `path`: Path to test location (app dir or SDK root)
- `test_type`: Type of tests - "app", "sdk_unit", or "sdk_integration" (auto-detected if not specified)
- `test_path`: Specific test file/directory (optional)
- `soar_instance`: For integration tests: `{"ip": "10.1.19.88", "username": "admin", "password": "pass"}`
- `max_iterations`: Maximum fix attempts (default: 5)
- `verbose`: Enable verbose output

**Returns:**
- Final test status
- Summary of fixes applied
- Test output
- Test type detected/used

## Installation

1. Install dependencies:
```bash
cd /path/to/splunk-soar-sdk/mcp_server
uv sync
```

2. Add to your Claude Code MCP settings (`~/.claude/mcp_settings.json` or via Claude Code UI):

```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server",
        "soar_test_assistant"
      ]
    }
  }
}
```

**Note**: Replace `/Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server` with the actual path to your mcp_server directory.

## Usage

Once installed, the tools are available in Claude Code:

### Fix App Tests
```
"Run and fix tests for tests/example_app"
```

### Fix SDK Unit Tests
```
"Run and fix SDK unit tests"
```

### Fix SDK Integration Tests
```
"Run and fix SDK integration tests against 10.1.19.88
(username: admin, password: password)"
```

Claude Code will automatically use the right test type!

## Development

The server is built using the official Python MCP SDK:
- `mcp`: Model Context Protocol SDK
- Integrates with `soarapps` CLI commands
- Uses pytest output parsing for analysis
