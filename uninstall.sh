#!/bin/bash
# Code-MCP Uninstallation Script
# https://github.com/54yyyu/code-mcp

set -e

# Text colors
BOLD="$(tput bold 2>/dev/null || echo '')"
BLUE="$(tput setaf 4 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
RED="$(tput setaf 1 2>/dev/null || echo '')"
NC="$(tput sgr0 2>/dev/null || echo '')" # No Color

# Functions for log messages
info() {
  echo -e "${BOLD}${BLUE}INFO${NC}: $1"
}

success() {
  echo -e "${BOLD}${GREEN}SUCCESS${NC}: $1"
}

warn() {
  echo -e "${BOLD}${YELLOW}WARNING${NC}: $1"
}

error() {
  echo -e "${BOLD}${RED}ERROR${NC}: $1"
  exit 1
}

# Print logo and header
echo -e "${BLUE}"
echo "  _____           _        __  __  _____ _____  "
echo " / ____|         | |      |  \/  |/ ____|  __ \ "
echo "| |     ___   __| | ___  | \  / | |    | |__) |"
echo "| |    / _ \ / _\` |/ _ \ | |\/| | |    |  ___/ "
echo "| |___| (_) | (_| |  __/ | |  | | |____| |     "
echo " \_____\___/ \__,_|\___| |_|  |_|\_____|_|     "
echo -e "${NC}"
echo "Code-MCP Uninstallation Script"
echo "========================================"
echo

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Uninstall Code-MCP
info "Uninstalling Code-MCP..."

if command_exists uv; then
  info "Using uv package manager"
  uv pip uninstall -y code-mcp
elif command_exists pip3; then
  warn "Using pip3 instead of uv"
  pip3 uninstall -y code-mcp
elif command_exists pip; then
  warn "Using pip instead of uv"
  pip uninstall -y code-mcp
else
  error "Neither uv nor pip found. Cannot uninstall Code-MCP."
fi

success "Code-MCP uninstalled successfully!"

# Check for Claude Desktop config
check_claude_config() {
  config_found=0
  
  # Check common locations for Claude Desktop config
  for config_path in \
    "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
    "$HOME/Library/Application Support/Claude/config/claude_desktop_config.json" \
    "$HOME/.config/Claude/config/claude_desktop_config.json" \
    "$APPDATA/Claude/config/claude_desktop_config.json"
  do
    if [ -f "$config_path" ]; then
      config_found=1
      warn "Claude Desktop configuration found at: $config_path"
      echo "You may want to manually remove the 'code' entry from the mcpServers section."
      echo "Example of what to remove:"
      echo '    "mcpServers": {'
      echo '        "code": {'
      echo '            "command": "code-mcp",'
      echo '            "args": ['
      echo '                "/path/to/your/project"'
      echo '            ]'
      echo '        }'
      echo '    }'
      break
    fi
  done
  
  if [ "$config_found" -eq 0 ]; then
    info "Claude Desktop configuration not found."
  fi
}

check_claude_config

echo
success "Uninstallation complete!"
