#!/bin/bash
# Code-MCP Installation Script
# https://github.com/54yyyu/code-mcp
# Usage: curl -LsSf https://raw.githubusercontent.com/54yyyu/code-mcp/main/install.sh | sh

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

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
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
echo "Code-MCP Installation Script"
echo "========================================"
echo "Terminal & Code Control for Claude AI"
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
  Linux)
    OS="linux"
    ;;
  Darwin)
    OS="macos"
    ;;
  MINGW* | MSYS* | CYGWIN* | Windows_NT)
    OS="windows"
    error "Windows detected - please use the Windows installer (install.bat or install.ps1)"
    ;;
  *)
    error "Unsupported operating system: $OS"
    ;;
esac

info "Detected OS: $OS"

# Install uv if not present
install_uv() {
  info "Installing uv package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  
  # Update PATH for current session
  if [[ -z "${UV_BIN_PATH}" ]]; then
    export PATH="${HOME}/.astral/uv/bin:${PATH}"
  fi
  
  # Check if shell config files exist and add uv to PATH
  if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "astral/uv/bin" "$HOME/.bashrc"; then
      echo 'export PATH="${HOME}/.astral/uv/bin:${PATH}"' >> "$HOME/.bashrc"
      info "Added uv to PATH in .bashrc"
    fi
  elif [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "astral/uv/bin" "$HOME/.zshrc"; then
      echo 'export PATH="${HOME}/.astral/uv/bin:${PATH}"' >> "$HOME/.zshrc"
      info "Added uv to PATH in .zshrc"
    fi
  else
    warn "Please add the following to your shell profile:"
    echo 'export PATH="${HOME}/.astral/uv/bin:${PATH}"'
  fi
  
  # Verify uv installation
  if command_exists uv; then
    success "uv installed successfully!"
  else
    warn "uv installation complete but command not found in PATH"
    warn "You may need to restart your terminal or manually set PATH"
  fi
}

# Check if Python is installed
info "Checking for Python..."
if command_exists python3; then
  PYTHON_CMD="python3"
elif command_exists python; then
  # Check if Python is version 3
  if python --version 2>&1 | grep -q "Python 3"; then
    PYTHON_CMD="python"
  else
    error "Python 3 is required (Python 2 detected)"
  fi
else
  error "Python 3 not found. Please install Python 3.10 or newer."
fi

# Verify Python version
PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
  error "Python 3.10 or newer is required (detected $PY_VERSION)"
fi

success "Python $PY_VERSION detected"

# Check if uv is installed, install if not
if ! command_exists uv; then
  warn "uv package manager not found"
  echo -n "Would you like to install uv for better dependency management? (y/N) "
  read -r REPLY
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    install_uv
  else
    warn "Skipping uv installation, will use pip if available"
  fi
fi

# Install code-mcp
info "Installing code-mcp..."

if command_exists uv; then
  info "Using uv package manager"
  uv pip install git+https://github.com/54yyyu/code-mcp.git
elif command_exists pip3; then
  warn "Using pip3 instead of uv"
  pip3 install git+https://github.com/54yyyu/code-mcp.git
elif command_exists pip; then
  warn "Using pip instead of uv"
  pip install git+https://github.com/54yyyu/code-mcp.git
else
  error "Neither uv nor pip found. Please install pip or uv and try again."
fi

# Verify installation
if command_exists code-mcp; then
  VERSION=$(code-mcp --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' || echo "Unknown")
  success "Installation successful! Code-MCP version $VERSION"
  
  echo ""
  echo -e "${BLUE}=== Getting Started ===${NC}"
  echo ""
  echo "To set up Claude Desktop integration:"
  echo ""
  echo "1. Run the setup helper:"
  echo "   code-mcp-setup /path/to/your/project"
  echo ""
  echo "2. Or manually add to Claude Desktop config (claude_desktop_config.json):"
  echo "   Typically found at: ~/Library/Application Support/Claude/claude_desktop_config.json"
  echo '   "mcpServers": {'
  echo '     "code": {'
  echo '       "command": "code-mcp",'
  echo '       "args": ['
  echo '         "/path/to/your/project"'
  echo '       ]'
  echo '     }'
  echo '   }'
  echo ""
  echo "3. Restart Claude Desktop"
else
  error "Installation failed. Try installing manually: pip install git+https://github.com/54yyyu/code-mcp.git"
fi

echo ""
success "Installation complete!"
