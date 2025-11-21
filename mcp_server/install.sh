#!/bin/bash
set -e

echo "Installing SOAR Test Assistant MCP Server..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CONFIG_DIR="$HOME/.config/claude-code"
MCP_CONFIG_FILE="$MCP_CONFIG_DIR/mcp_settings.json"

echo "1. Installing dependencies..."
cd "$SCRIPT_DIR"
uv sync

echo "2. Setting up MCP configuration..."
mkdir -p "$MCP_CONFIG_DIR"

SERVER_NAME="soar-test-assistant"
SERVER_CONFIG=$(cat <<EOF
{
  "command": "uv",
  "args": [
    "run",
    "--directory",
    "$SCRIPT_DIR",
    "soar_test_assistant"
  ]
}
EOF
)

if [ -f "$MCP_CONFIG_FILE" ]; then
    echo "   MCP config file exists, backing up..."
    cp "$MCP_CONFIG_FILE" "$MCP_CONFIG_FILE.backup.$(date +%s)"

    if command -v jq &> /dev/null; then
        echo "   Adding server to existing config..."
        jq ".mcpServers[\"$SERVER_NAME\"] = $SERVER_CONFIG" "$MCP_CONFIG_FILE" > "$MCP_CONFIG_FILE.tmp"
        mv "$MCP_CONFIG_FILE.tmp" "$MCP_CONFIG_FILE"
    else
        echo "   WARNING: jq not found. Please manually add the server to $MCP_CONFIG_FILE"
        echo "   Server configuration:"
        echo "$SERVER_CONFIG"
    fi
else
    echo "   Creating new MCP config file..."
    cat > "$MCP_CONFIG_FILE" <<EOF
{
  "mcpServers": {
    "$SERVER_NAME": $SERVER_CONFIG
  }
}
EOF
fi

echo ""
echo "Installation complete!"
echo ""
echo "Restart Claude Code to load the new MCP server."
