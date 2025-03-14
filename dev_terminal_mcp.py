import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
import git
from mcp.server.fastmcp import FastMCP, Context

# Initialize FastMCP server
mcp = FastMCP("DevTerminal")

# Get the project root directory from command line arguments or use current directory
PROJECT_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).absolute()
print(f"[DevTerminal MCP] Initializing with project root: {PROJECT_ROOT}", file=sys.stderr)

# Validate that the directory exists
if not PROJECT_ROOT.exists():
    print(f"[DevTerminal MCP] Error: Project directory {PROJECT_ROOT} does not exist", file=sys.stderr)
    sys.exit(1)

# Security check to prevent access outside the project directory
def is_safe_path(path: Path) -> bool:
    """Check if the path is within the project directory"""
    try:
        return PROJECT_ROOT in path.absolute().parents or path.absolute() == PROJECT_ROOT
    except (ValueError, FileNotFoundError):
        return False

# Helper functions
def safe_read_file(file_path: Path) -> str:
    """Safely read a file, ensuring it's within the project directory"""
    if not is_safe_path(file_path):
        raise ValueError(f"Cannot access file outside project directory: {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if file_path.is_dir():
        raise IsADirectoryError(f"Cannot read directory as file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        return f"[Binary file: {file_path.name}]"

# Resource for accessing files
@mcp.resource("file://{file_path}")
def get_file(file_path: str) -> str:
    """Get the contents of a file within the project directory."""
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    return safe_read_file(path)

# Resource for listing directory contents
@mcp.resource("dir://{dir_path}")
def list_directory(dir_path: str) -> str:
    """List the contents of a directory within the project directory."""
    path = Path(dir_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    if not is_safe_path(path):
        raise ValueError(f"Cannot access directory outside project directory: {path}")
    
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    
    try:
        # List files and directories
        items = list(path.iterdir())
        dirs = [f"📁 {item.name}/" for item in items if item.is_dir()]
        files = [f"📄 {item.name}" for item in items if item.is_file()]
        
        # Sort alphabetically
        dirs.sort()
        files.sort()
        
        # Format the output
        output = f"Contents of {path}:\n\n"
        if dirs:
            output += "Directories:\n" + "\n".join(dirs) + "\n\n"
        if files:
            output += "Files:\n" + "\n".join(files)
        
        return output
    except PermissionError:
        raise PermissionError(f"Permission denied when accessing directory: {path}")

# Resource for project structure
@mcp.resource("project://structure")
def get_project_structure() -> str:
    """Get a tree-like view of the project structure."""
    
    def generate_tree(directory: Path, prefix: str = '', is_last: bool = True, max_depth: int = 3, current_depth: int = 0) -> str:
        if current_depth > max_depth:
            return prefix + "...\n"
        
        # Skip hidden files and directories
        if directory.name.startswith('.') and directory != PROJECT_ROOT:
            return ""
        
        # Format the current directory
        output = prefix + ('└── ' if is_last else '├── ') + directory.name + '/\n'
        
        # Get items in the directory
        try:
            items = sorted(list(directory.iterdir()), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            return output + prefix + ('    ' if is_last else '│   ') + "[Permission denied]\n"
        
        # Process each item
        for i, item in enumerate(items):
            # Skip hidden items
            if item.name.startswith('.'):
                continue
                
            is_last_item = i == len(items) - 1
            new_prefix = prefix + ('    ' if is_last else '│   ')
            
            if item.is_dir():
                output += generate_tree(item, new_prefix, is_last_item, max_depth, current_depth + 1)
            else:
                output += new_prefix + ('└── ' if is_last_item else '├── ') + item.name + '\n'
        
        return output
    
    return generate_tree(PROJECT_ROOT, current_depth=0)

# Tool for running shell commands
@mcp.tool()
async def run_command(command: str, ctx: Context) -> str:
    """
    Execute a shell command and return its output.
    
    Args:
        command: The shell command to execute
    """
    try:
        # Security check - reject commands with dangerous operators
        dangerous_operators = [';', '&&', '||', '>', '>>', '|', '<']
        if any(op in command for op in dangerous_operators):
            return f"Error: Command contains potentially dangerous operators: {command}"
        
        # Log the command
        ctx.info(f"Executing command: {command}")
        
        # Run the command
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=30)
        
        # Format the output
        output = ""
        if stdout:
            output += f"STDOUT:\n{stdout}\n"
        if stderr:
            output += f"STDERR:\n{stderr}\n"
        
        return output.strip() or "Command executed successfully (no output)"
    
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out"
    except Exception as e:
        return f"Error executing command: {str(e)}"

# Tool for git operations
@mcp.tool()
async def git_operation(operation: str, ctx: Context) -> str:
    """
    Execute a git operation in the project repository.
    
    Args:
        operation: The git operation to perform (e.g., "status", "log", "branch")
    """
    try:
        # Check if the project directory is a git repository
        repo_path = PROJECT_ROOT
        if not (repo_path / '.git').exists():
            return "Error: The project directory is not a git repository"
        
        # Security check - reject dangerous git operations
        dangerous_operations = ["push", "reset --hard", "clean -f"]
        if any(op in operation for op in dangerous_operations):
            return f"Error: Potentially destructive git operation not allowed: {operation}"
        
        # Log the operation
        ctx.info(f"Executing git operation: {operation}")
        
        # Execute the git command
        command = f"git {operation}"
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_path,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=30)
        
        # Format the output
        output = ""
        if stdout:
            output += f"STDOUT:\n{stdout}\n"
        if stderr:
            output += f"STDERR:\n{stderr}\n"
        
        return output.strip() or "Git operation executed successfully (no output)"
    
    except subprocess.TimeoutExpired:
        return "Error: Git operation timed out"
    except Exception as e:
        return f"Error executing git operation: {str(e)}"

# Tool for writing to files (requires permission)
@mcp.tool()
async def write_file(file_path: str, content: str, ctx: Context) -> str:
    """
    Write content to a file within the project directory.
    
    Args:
        file_path: Path to the file (relative to project root or absolute)
        content: Content to write to the file
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot write to file outside project directory: {path}"
    
    # Check if we're creating a new file or overwriting
    action = "Create new file" if not path.exists() else "Overwrite existing file"
    
    # Log the request
    ctx.info(f"Request to {action.lower()}: {path}")
    
    # Return a preview of what will be written
    preview = content[:500] + "..." if len(content) > 500 else content
    return f"""{action}: {path}
    
Content Preview:
```
{preview}
```

NOTE: This is just a preview. To actually write the file, use the `confirm_write_file` tool with the same parameters."""

# Tool for confirming file write
@mcp.tool()
async def confirm_write_file(file_path: str, content: str, ctx: Context) -> str:
    """
    Confirm and execute writing content to a file after user has reviewed the preview.
    
    Args:
        file_path: Path to the file (relative to project root or absolute)
        content: Content to write to the file
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot write to file outside project directory: {path}"
    
    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Log the action
        ctx.info(f"Successfully wrote to file: {path}")
        
        return f"Successfully wrote {len(content)} bytes to {path}"
    
    except PermissionError:
        return f"Error: Permission denied when writing to file: {path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

# Tool for creating directories
@mcp.tool()
async def create_directory(dir_path: str, ctx: Context) -> str:
    """
    Create a directory within the project.
    
    Args:
        dir_path: Path to the directory to create (relative to project root or absolute)
    """
    path = Path(dir_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot create directory outside project directory: {path}"
    
    try:
        # Check if the directory already exists
        if path.exists():
            return f"Directory already exists: {path}"
        
        # Create the directory
        path.mkdir(parents=True)
        
        # Log the action
        ctx.info(f"Created directory: {path}")
        
        return f"Successfully created directory: {path}"
    
    except PermissionError:
        return f"Error: Permission denied when creating directory: {path}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"

# Tool for deleting files or directories
@mcp.tool()
async def delete_path(path_to_delete: str, ctx: Context) -> str:
    """
    Request to delete a file or directory within the project.
    
    Args:
        path_to_delete: Path to delete (relative to project root or absolute)
    """
    path = Path(path_to_delete)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot delete path outside project directory: {path}"
    
    # Check if the path exists
    if not path.exists():
        return f"Error: Path does not exist: {path}"
    
    # Log the request
    if path.is_dir():
        ctx.info(f"Request to delete directory: {path}")
        return f"""Request to delete directory: {path}
        
This will remove the directory and all its contents. To confirm deletion, use the `confirm_delete_path` tool with the same path."""
    else:
        ctx.info(f"Request to delete file: {path}")
        return f"""Request to delete file: {path}
        
To confirm deletion, use the `confirm_delete_path` tool with the same path."""

# Tool for confirming deletion
@mcp.tool()
async def confirm_delete_path(path_to_delete: str, ctx: Context) -> str:
    """
    Confirm and execute deletion of a file or directory after user has reviewed the request.
    
    Args:
        path_to_delete: Path to delete (relative to project root or absolute)
    """
    path = Path(path_to_delete)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot delete path outside project directory: {path}"
    
    # Check if the path exists
    if not path.exists():
        return f"Error: Path does not exist: {path}"
    
    try:
        if path.is_dir():
            # Delete directory
            shutil.rmtree(path)
            ctx.info(f"Successfully deleted directory: {path}")
            return f"Successfully deleted directory: {path}"
        else:
            # Delete file
            path.unlink()
            ctx.info(f"Successfully deleted file: {path}")
            return f"Successfully deleted file: {path}"
    
    except PermissionError:
        return f"Error: Permission denied when deleting: {path}"
    except Exception as e:
        return f"Error deleting path: {str(e)}"

# Run the server
if __name__ == "__main__":
    mcp.run()