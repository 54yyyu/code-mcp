# Open Claude Code

A secure and professional development terminal for executing commands, managing files, and interacting with Git repositories within defined project boundaries.

## Overview

Open Claude Code is a Python-based tool that provides a controlled environment for executing commands and managing files within a project directory. It enforces security boundaries to prevent access outside the specified project root, making it suitable for integration with AI assistants or other automated systems.

## Features

- **Command Execution**: Run shell commands safely within the project directory
- **File Operations**:
  - Read file contents
  - Edit files with various operations (write, append, insert, replace, delete)
  - Enhanced smart editing with function-level operations and improved pattern matching
  - List directory contents
  - Create directories
  - Delete files or directories with confirmation
- **Git Integration**: Execute git operations within the repository with confirmation for sensitive operations
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

- `run_command(command: str)` - Execute a shell command and return its output
- `git_operation(operation: str, confirm: bool = False)` - Execute a git operation in the project repository with confirmation for sensitive operations
- `read_file(file_path: str)` - Read the contents of a file within the project directory
- `edit_file(file_path: str, operation: str, content: str = "", line_number: int = None, pattern: str = None, start_line: int = None, end_line: int = None, confirm: bool = False)` - Edit a file with various operations:
  - `write` - Completely replace file contents
  - `append` - Add content to the end of the file
  - `insert` - Insert content at a specific line number
  - `replace` - Replace occurrences of a pattern with new content
  - `delete` - Delete all occurrences of a pattern
  - `delete_lines` - Delete specific lines by line numbers
- `create_directory(dir_path: str)` - Create a directory within the project
- `delete_path(path_to_delete: str, confirm: bool = False)` - Delete a file or directory within the project
- `smart_edit(file_path: str, operation: str = "preview", function_name: str = None, pattern: str = None, new_content: str = None, regex_mode: bool = False, context_lines: int = 3, confirm: bool = False)` - Enhanced file editing with:
  - Function-level operations for updating entire functions at once
  - Smart pattern matching with flexible whitespace handling
  - Regex pattern support for advanced matching
  - Better context in previews and error messages
  - Helpful suggestions when patterns aren't found

## Testing

You can test this server with both the Claude Desktop app and the MCP Inspector:

### Testing with Claude Desktop

1. Edit your Claude Desktop configuration file:
   ```
   # macOS
   ~/Library/Application Support/Claude/claude_desktop_config.json
   # Windows
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. Add the server configuration:
   ```json
   {
     "mcpServers": {
       "open-claude-code": {
         "command": "python",
         "args": ["/absolute/path/to/dev_terminal_mcp.py", "/path/to/project/directory"]
       }
     }
   }
   ```

3. Restart Claude Desktop and interact with the server through the Claude chat interface

### Testing with MCP Inspector

You can use the MCP Inspector to test and debug this server:

```bash
npx @modelcontextprotocol/inspector python /path/to/dev_terminal_mcp.py /path/to/project/directory
```

## Security Considerations

The tool implements several security measures:
- Path validation to ensure operations only occur within the project directory
- Rejection of shell commands with dangerous operators (`;`, `&&`, `||`, etc.)
- Different security levels for git operations: some blocked entirely, others requiring confirmation
- Two-step confirmation process for file writes and deletions

## Dependencies

- MCP for server implementation
- Python standard libraries (os, sys, shutil, subprocess, pathlib)

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.