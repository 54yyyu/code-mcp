#!/bin/bash
#
# Remote Code-MCP Bridge - One-line installer
#
# This script automatically:
# 1. Installs code-mcp locally if needed
# 2. Sets up the remote bridge to connect to a specified server
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/54yyyu/code-mcp/remote-edit/remote-install.sh | bash -s -- [OPTIONS]
#
# Options:
#   --remote-host HOST       Remote host to connect to (required, e.g. user@hostname)
#   --remote-project-path    Path to the project directory on the remote host (default: ~/project)
#   --local-port PORT        Local port for the SSH tunnel (default: 3000)
#   --remote-port PORT       Remote port for the bridge server (default: 5000)
#   --ssh-key PATH           Path to SSH private key file (optional)
#

set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Print banner
echo "================================================="
echo "  Remote Code-MCP Bridge - One-line Installer"
echo "================================================="
echo ""

# Check for required tools
for cmd in python3 pip git ssh; do
    if ! command_exists $cmd; then
        echo "Error: $cmd is required but not installed. Please install it first."
        exit 1
    fi
done

# Parse arguments
REMOTE_HOST=""
REMOTE_PROJECT_PATH="~/project"
LOCAL_PORT=3000
REMOTE_PORT=5000
SSH_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remote-host)
            REMOTE_HOST="$2"
            shift 2
            ;;
        --remote-project-path)
            REMOTE_PROJECT_PATH="$2"
            shift 2
            ;;
        --local-port)
            LOCAL_PORT="$2"
            shift 2
            ;;
        --remote-port)
            REMOTE_PORT="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Verify required arguments
if [ -z "$REMOTE_HOST" ]; then
    echo "Error: --remote-host is required"
    echo "Usage: curl -sSL https://raw.githubusercontent.com/54yyyu/code-mcp/remote-edit/remote-install.sh | bash -s -- --remote-host user@hostname [OPTIONS]"
    exit 1
fi

# Check if code-mcp is already installed
echo "Checking for code-mcp installation..."
if ! command_exists code-mcp; then
    echo "code-mcp not found, installing..."
    
    # Try to use uv if available (faster)
    if command_exists uv; then
        echo "Installing with uv..."
        uv pip install "git+https://github.com/54yyyu/code-mcp.git@remote-edit"
    else
        echo "Installing with pip..."
        python3 -m pip install --user "git+https://github.com/54yyyu/code-mcp.git@remote-edit"
    fi
    
    echo "code-mcp installed successfully"
else
    echo "code-mcp is already installed"
    
    # Check if it's the remote-edit version
    echo "Checking for the remote-edit version..."
    
    # Try to update to the remote-edit branch
    if command_exists uv; then
        echo "Updating to the remote-edit branch with uv..."
        uv pip install --force-reinstall "git+https://github.com/54yyyu/code-mcp.git@remote-edit"
    else
        echo "Updating to the remote-edit branch with pip..."
        python3 -m pip install --user --force-reinstall "git+https://github.com/54yyyu/code-mcp.git@remote-edit"
    fi
fi

# Build the command for the remote setup
CMD="code-mcp-remote --remote-host \"$REMOTE_HOST\" --remote-project-path \"$REMOTE_PROJECT_PATH\" --local-port $LOCAL_PORT --remote-port $REMOTE_PORT"

if [ -n "$SSH_KEY" ]; then
    CMD="$CMD --ssh-key \"$SSH_KEY\""
fi

echo ""
echo "Starting the remote bridge setup..."
echo "Connecting to $REMOTE_HOST..."
echo ""

# Run the remote setup
eval $CMD

# End of script
