# Open Claude Code

A secure and professional development terminal for executing commands, managing files, and interacting with Git repositories within defined project boundaries.

## Overview

Open Claude Code is a Python-based tool that provides a controlled environment for executing commands and managing files within a project directory. It enforces security boundaries to prevent access outside the specified project root, making it suitable for integration with AI assistants or other automated systems.

## Features

- **Command Execution**: Run shell commands safely within the project directory
- **File Operations**:
  - Read file contents
  - Create and write to files with preview and confirmation steps
  - List directory contents
  - Create directories
  - Delete files or directories with confirmation
- **Git Integration**: Execute git operations within the repository
- **Project Navigation**: Get a tree-like view of the project structure
- **Security Measures**:
  - Path validation to prevent access outside project root
  - Dangerous command detection
  - Two-step confirmation for file modifications and deletions

## Installation

```bash
# Clone the repository
git clone https://github.com/54yyyu/open-claude-code.git
cd open-claude-code

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python dev_terminal_mcp.py [project_root_directory]
```

If no project root is specified, the current working directory will be used.

## API

### Resources

- `file://{file_path}` - Get the contents of a file
- `dir://{dir_path}` - List the contents of a directory
- `project://structure` - Get a tree-like view of the project structure

### Tools

- `run_command(command: str)` - Execute a shell command
- `git_operation(operation: str)` - Execute a git operation
- `write_file(file_path: str, content: str)` - Preview writing to a file
- `confirm_write_file(file_path: str, content: str)` - Confirm and execute file write
- `create_directory(dir_path: str)` - Create a directory
- `delete_path(path_to_delete: str)` - Request to delete a file or directory
- `confirm_delete_path(path_to_delete: str)` - Confirm and execute deletion

## Security Considerations

The tool implements several security measures:
- Path validation to ensure operations only occur within the project directory
- Rejection of shell commands with dangerous operators (`;`, `&&`, `||`, etc.)
- Rejection of potentially destructive git operations
- Two-step confirmation process for file writes and deletions

## Dependencies

- MCP (for server implementation)
- GitPython
- Python standard libraries (os, sys, shutil, subprocess, pathlib)

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.