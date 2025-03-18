# Code-MCP: Terminal and Code Integration for Claude AI

Code-MCP connects Claude AI to your development environment through the Model Context Protocol (MCP), enabling terminal commands and file operations through the AI interface.

## Features

- **Terminal Access**: Run shell commands in your project directory directly from Claude
- **File Operations**: Create, read, update, and delete files and directories
- **Git Integration**: Special handling for git commands with safety confirmations
- **Smart Editing**: Enhanced editing capabilities for code files
- **Code Analysis**: Advanced pattern matching and function-level operations
- **Productivity Tools**: Operate on your codebase with natural language instructions

## Quick Installation

### macOS / Linux

```bash
# Install with a single command (includes uv installation if needed)
curl -LsSf https://raw.githubusercontent.com/54yyyu/code-mcp/main/install.sh | sh
```

### Windows

```powershell
# Download and run the installer
powershell -c "Invoke-WebRequest -Uri https://raw.githubusercontent.com/54yyyu/code-mcp/main/install.ps1 -OutFile install.ps1; .\install.ps1"
```

### Manual Installation

```bash
# Install with pip
pip install git+https://github.com/54yyyu/code-mcp.git

# Or better, install with uv
uv pip install git+https://github.com/54yyyu/code-mcp.git
```

### For Developers

If you're developing Code-MCP, clone the repository and install in development mode:

```bash
# Clone the repository
git clone https://github.com/54yyyu/code-mcp.git
cd code-mcp

# Install in development mode with pip
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

## Usage

### Claude Desktop Integration

1. Automatic setup:
   ```bash
   code-mcp-setup /path/to/your/project
   ```

2. Or manually edit Claude Desktop configuration:
   - Go to Claude > Settings > Developer > Edit Config
   - Add the following to your `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "code": {
            "command": "code-mcp",
            "args": [
                "/path/to/your/project"
            ]
        }
    }
}
```

3. Save the file and restart Claude

## Features

### Terminal Operations

- Execute terminal commands with `run_command()`
- Perform git operations with `git_operation()`

### File Operations

- Read files with `read_file()`
- Edit files with `edit_file()` and `smart_edit()`
- Create and delete directories with `create_directory()` and `delete_path()`
- List directory contents with `list_directory()`

### Advanced Code Editing

- Flexible pattern matching with whitespace normalization
- Function-level editing with automatic indentation handling
- Batch operations across multiple files with `edit_block()`
- Support for search/replace blocks and unified diff formats

## Examples

Ask Claude:

- "List all the files in the current directory"
- "Show me the content of the README.md file"
- "Create a new file called example.py with a simple hello world program"
- "Run git status and show me what files have changed"
- "Make these changes to main.py: replace X with Y"
- "Update the process_data function in data_utils.py to handle null values"

## Safety Features

- Confirmation required for destructive operations (delete, overwrite)
- Path safety to prevent operations outside project directory
- Special confirmation for potentially dangerous git commands

## Requirements

- Python 3.10 or newer
- Claude Desktop or API access
- Git (optional, for git operations)

## License

This project is licensed under the MIT License - see the LICENSE file for details.