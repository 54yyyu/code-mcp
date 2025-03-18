# Code-MCP Installation Script for Windows
# https://github.com/54yyyu/code-mcp
# Usage: Invoke-WebRequest -Uri https://raw.githubusercontent.com/54yyyu/code-mcp/main/install.ps1 | Invoke-Expression

function Write-Info {
    Write-Host "INFO: $args" -ForegroundColor Blue
}

function Write-Warning {
    Write-Host "WARNING: $args" -ForegroundColor Yellow
}

function Write-Error {
    Write-Host "ERROR: $args" -ForegroundColor Red
    exit 1
}

function Write-Success {
    Write-Host "SUCCESS: $args" -ForegroundColor Green
}

function Test-Command {
    param (
        [string]$Command
    )
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Display banner
Write-Host ""
Write-Host "  _____           _        __  __  _____ _____  " -ForegroundColor Cyan
Write-Host " / ____|         | |      |  \/  |/ ____|  __ \ " -ForegroundColor Cyan
Write-Host "| |     ___   __| | ___  | \  / | |    | |__) |" -ForegroundColor Cyan
Write-Host "| |    / _ \ / _\` |/ _ \ | |\/| | |    |  ___/ " -ForegroundColor Cyan
Write-Host "| |___| (_) | (_| |  __/ | |  | | |____| |     " -ForegroundColor Cyan
Write-Host " \_____\___/ \__,_|\___| |_|  |_|\_____|_|     " -ForegroundColor Cyan
Write-Host ""
Write-Host "Code-MCP Installation Script" -ForegroundColor Cyan
Write-Host "========================================"
Write-Host "Terminal & Code Control for Claude AI"
Write-Host ""

# Check for Python
Write-Info "Checking for Python..."
if (Test-Command python) {
    # Check if it's actually Python 3
    $version = python --version 2>&1
    if ($version -match "Python 3") {
        $PYTHON = "python"
    }
    else {
        Write-Error "Python 3 is required (Python 2 detected)"
    }
}
else {
    Write-Error "Python 3 not found. Please install Python 3.10 or newer."
}

# Ensure Python version is at least 3.10
$pythonVersionStr = & $PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pythonVersion = [version]$pythonVersionStr
if ($pythonVersion -lt [version]"3.10") {
    Write-Error "Python 3.10 or newer is required (found $pythonVersionStr)"
}

Write-Success "Python $pythonVersionStr detected"

# Check for and install uv if needed
if (-not (Test-Command uv)) {
    Write-Warning "uv package manager not found"
    $installUv = Read-Host "Would you like to install uv for better dependency management? (y/N)"
    if ($installUv -match "^[Yy]") {
        Write-Info "Installing uv package manager..."
        Invoke-RestMethod -Uri https://astral.sh/uv/install.ps1 | Invoke-Expression
        
        # Verify uv installation
        if (Test-Command uv) {
            Write-Success "uv installed successfully!"
        }
        else {
            Write-Warning "uv installation complete but command not found in PATH"
            Write-Warning "You may need to restart your PowerShell session to use uv"
            
            # Try to add to PATH for current session
            $uvPath = "$env:USERPROFILE\.astral\uv\bin"
            if (Test-Path $uvPath) {
                $env:PATH = "$uvPath;$env:PATH"
                Write-Info "Added uv to PATH for current session"
            }
        }
    }
    else {
        Write-Warning "Skipping uv installation, will use pip if available"
    }
}

# Install code-mcp
Write-Info "Installing code-mcp..."

if (Test-Command uv) {
    Write-Info "Using uv package manager"
    uv pip install git+https://github.com/54yyyu/code-mcp.git
}
elseif (Test-Command pip) {
    Write-Warning "Using pip instead of uv"
    pip install git+https://github.com/54yyyu/code-mcp.git
}
else {
    Write-Error "Neither uv nor pip found. Please install pip or uv and try again."
}

# Verify installation
if (Test-Command code-mcp) {
    $version = (code-mcp --version 2>&1) -replace ".*?(\d+\.\d+\.\d+).*", '$1'
    Write-Success "Installation successful! Code-MCP version $version"
    
    Write-Host ""
    Write-Host "=== Getting Started ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To set up Claude Desktop integration:"
    Write-Host ""
    Write-Host "1. Run the setup helper:"
    Write-Host "   code-mcp-setup C:\path\to\your\project"
    Write-Host ""
    Write-Host "2. Or manually add to Claude Desktop config (claude_desktop_config.json):"
    Write-Host '   "mcpServers": {'
    Write-Host '     "code": {'
    Write-Host '       "command": "code-mcp",'
    Write-Host '       "args": ['
    Write-Host '         "C:\path\to\your\project"'
    Write-Host '       ]'
    Write-Host '     }'
    Write-Host '   }'
    Write-Host ""
    Write-Host "3. Restart Claude Desktop"
}
else {
    Write-Error "Installation failed. Try installing manually: pip install git+https://github.com/54yyyu/code-mcp.git"
}

Write-Host ""
Write-Success "Installation complete!"
