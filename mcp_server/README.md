# SOAR Test Assistant MCP Server

An MCP (Model Context Protocol) server that provides AI-powered test analysis and auto-fixing for Splunk SOAR SDK and apps.

## Features

- **Automatic Test Fixing**: Iteratively runs tests, analyzes failures, and applies fixes until passing
- **Intelligent Analysis**: Identifies root causes and distinguishes SDK bugs from app bugs
- **Multi-Test Support**: Works with app tests, SDK unit tests, and SDK integration tests
- **Auto-Detection**: Automatically detects test type based on project structure

## Installation

### Quick Install

```bash
cd mcp_server
./install.sh
```

This will install dependencies and configure the MCP server in Claude Code.

### Manual Install

1. Install dependencies:
```bash
cd mcp_server
uv sync
```

2. Add to your MCP settings file (location varies by OS):
   - macOS: `~/.config/claude-code/mcp_settings.json`
   - Linux: `~/.config/claude-code/mcp_settings.json`
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

3. Restart Claude Code

## Usage

Once installed, use the tools naturally in Claude Code:

### Run and Fix Tests Automatically

```
Can you run tests for the example app and auto-fix any failures?
```

```
Run and fix SDK unit tests
```

```
Run and fix SDK integration tests against 10.1.19.88
(username: admin, password: password)
```

### Analyze Test Output

```
I have this pytest output: [paste output]
Can you analyze what's wrong?
```

### Manual Tool Usage

```
Use run_and_fix_tests on tests/example_app with max_iterations=10 and verbose=true
```

## MCP Tools

### `run_and_fix_tests`

Automatically runs tests, analyzes failures, applies fixes, and re-runs until all tests pass or max iterations reached.

**Parameters:**
- `path` (required): Path to test location (app dir or SDK root)
- `test_type` (optional): "app", "sdk_unit", or "sdk_integration" (auto-detected if not specified)
- `test_path` (optional): Specific test file or directory
- `soar_instance` (for integration tests): `{"ip": "10.1.19.88", "username": "admin", "password": "pass"}`
- `max_iterations` (optional): Maximum fix attempts (default: 5)
- `verbose` (optional): Enable verbose output (default: false)

**Returns:**
- Final test status
- Summary of fixes applied
- Test output

### `analyze_test_failure`

Analyzes pytest output to identify root causes and classify failures.

**Parameters:**
- `test_output` (required): Full pytest output
- `app_path` (optional): Path to app being tested

**Returns:**
- Analysis of test failures
- Classification (SDK bug vs app bug)
- Suggested fixes

### `fix_test_failure`

Applies automated fixes based on analysis.

**Parameters:**
- `failure_analysis` (required): JSON output from `analyze_test_failure`
- `app_path` (required): Path to app
- `auto_apply` (optional): Whether to automatically apply fixes (default: true)

**Returns:**
- List of files modified
- Changes applied

## How It Works

### Auto-Fix Flow

1. **Run Tests**: Executes appropriate test command based on type
2. **Analyze Failures**: Parses pytest output to identify:
   - Failed tests and error types
   - SDK bugs vs app bugs
   - Root causes
3. **Apply Fixes**: Automatically fixes common issues:
   - Missing dependencies → `uv add <package>`
   - Import errors → Install packages
4. **Re-run**: Repeats until tests pass or max iterations reached
5. **Report**: Provides summary of fixes applied

### Currently Auto-Fixable

- Missing Python packages (ImportError, ModuleNotFoundError)
- Simple dependency issues

### Requires Manual Review

- Assertion errors
- Type errors
- Attribute errors
- Fixture errors

## Configuration

The `[tool.uv.sources]` section in `pyproject.toml` allows using a local development version of `splunk-soar-sdk`:

```toml
[tool.uv.sources]
splunk-soar-sdk = { path = "..", editable = true }
```

When publishing or distributing, remove this section to use the PyPI version.

## Development

### Project Structure

```
mcp_server/
├── src/
│   └── soar_test_assistant/
│       ├── __init__.py
│       ├── server.py          # MCP server and tool handlers
│       ├── test_analyzer.py   # Pytest output analysis
│       └── test_fixer.py      # Automated fix application
├── tests/                     # Unit and integration tests
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

**Question: Should this be its own repo?**

**Current:** Lives in `splunk-soar-sdk/mcp_server/`

**Pros of keeping it in SDK repo:**
- Easier to develop in tandem with SDK
- Shares CI/CD infrastructure
- Natural versioning alignment
- Users find it when looking for SDK tools

**Pros of separate repo:**
- Independent release cycle
- Clearer ownership
- Easier to publish to MCP marketplace
- Can have different contributors/maintainers

**Recommendation:** Keep it in the SDK repo for now. If it gains significant usage or needs independent releases, split it later. The `[project.urls]` already points to the subdirectory which works fine for PyPI.

## Distribution & Publishing

MCP servers can be distributed in multiple ways:

### 1. Direct Installation (Recommended for Now)

Users install directly from the repository:

```bash
# Clone or download the repo
cd mcp_server
uv sync

# Add to Claude Code MCP settings
```

This is the simplest approach and works great for specialized tools.

### 2. PyPI Package

Publish as a Python package for easy installation:

```bash
# Prepare for publishing
# 1. Remove or comment out [tool.uv.sources] section in pyproject.toml
# 2. Build the package
uv build

# 3. Publish to PyPI
uv publish

# Users can then install with:
pip install soar-test-assistant
# or
uv pip install soar-test-assistant
```

### 3. MCP Marketplace (Future)

Anthropic is developing an official MCP marketplace/registry. When available, you can submit your MCP server there for discoverability.

**Current Status:** The MCP marketplace doesn't exist yet as a centralized registry. The Model Context Protocol is still young (2024).

**How users find MCP servers now:**
- GitHub repositories
- Documentation/blog posts
- Word of mouth
- MCP community listings (informal)

### 4. Claude Code Configuration

Users can reference your server in multiple ways:

**From Local Path:**
```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp_server", "soar_test_assistant"]
    }
  }
}
```

**From Installed Package:**
```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "soar_test_assistant"
    }
  }
}
```

### Recommendation for Now

1. **Keep in SDK repo** - Users who use the SDK will find it naturally
2. **Document in SDK README** - Add a section about the MCP server
3. **Optionally publish to PyPI** - Makes installation easier
4. **Wait for MCP marketplace** - Submit when it becomes available

The MCP ecosystem is still early, so direct distribution works perfectly fine.

## Support

- **SDK Issues**: https://github.com/phantomcyber/splunk-soar-sdk/issues
- **MCP Server Issues**: Use the same issue tracker with `[mcp-server]` label

## License

Apache License 2.0 - Copyright (c) 2024 Splunk Inc.

See [LICENSE](LICENSE) for full details.
