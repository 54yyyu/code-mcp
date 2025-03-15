import os
import sys
import shutil
import subprocess
import re
import difflib
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
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

def safe_read_file_lines(file_path: Path) -> List[str]:
    """Safely read a file as lines, ensuring it's within the project directory"""
    content = safe_read_file(file_path)
    return content.splitlines()

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

# Tool for reading files
@mcp.tool()
async def read_file(file_path: str, ctx: Context) -> str:
    """
    Read the contents of a file within the project directory.
    
    Args:
        file_path: Path to the file (relative to project root or absolute)
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot access file outside project directory: {path}"
    
    if not path.exists():
        return f"Error: File does not exist: {path}"
    
    if path.is_dir():
        return f"Error: Path is a directory, not a file: {path}"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        ctx.info(f"Successfully read file: {path}")
        return f"Contents of {path}:\n\n```\n{content}\n```"
    
    except UnicodeDecodeError:
        return f"Error: File appears to be binary and cannot be displayed as text: {path}"
    except PermissionError:
        return f"Error: Permission denied when reading file: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

# Tool for editing files with various operations
@mcp.tool()
async def edit_file(file_path: str, operation: str, ctx: Context, content: str = "", line_number: int = None, 
                    pattern: str = None, start_line: int = None, end_line: int = None, 
                    confirm: bool = False) -> str:
    """
    Edit a file with various operations: write, append, insert, replace, or delete.
    
    Args:
        file_path: Path to the file (relative to project root or absolute)
        operation: Type of edit ('write', 'append', 'insert', 'replace', 'delete', 'delete_lines')
        content: Content to write, append, or insert, or replacement content
        line_number: Line number for insert operation (1-based index) 
        pattern: Pattern to find for replace or delete operations
        start_line: First line to remove for delete_lines operation (1-based index)
        end_line: Last line to remove for delete_lines operation (1-based index, inclusive)
        confirm: Set to true to execute the edit, false to preview only
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot access file outside project directory: {path}"
    
    # Validate operation
    valid_operations = ['write', 'append', 'insert', 'replace', 'delete', 'delete_lines']
    if operation not in valid_operations:
        return f"Error: Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}"
    
    # Check for required parameters
    if operation == 'insert' and line_number is None:
        return "Error: Line number is required for insert operation"
    
    if operation in ['replace', 'delete'] and pattern is None:
        return f"Error: Pattern is required for {operation} operation"
        
    if operation == 'delete_lines' and (start_line is None or end_line is None):
        return "Error: start_line and end_line are required for delete_lines operation"
    
    # Preview or execute based on confirm flag
    try:
        # For existing files, show current content
        file_exists = path.exists()
        current_content = ""
        
        if file_exists and not path.is_dir():
            with open(path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        
        # Prepare preview of the changes
        if operation == 'write':
            new_content = content
            preview = f"Will completely replace file contents with new content."
        
        elif operation == 'append':
            new_content = current_content + content
            preview = f"Will append content to the end of the file."
        
        elif operation == 'insert':
            if file_exists:
                lines = current_content.splitlines()
                # Check line number validity
                if line_number < 1:
                    line_number = 1
                if line_number > len(lines) + 1:
                    line_number = len(lines) + 1
                
                # Insert at specified line (1-based index)
                lines.insert(line_number - 1, content)
                new_content = '\n'.join(lines)
                preview = f"Will insert content at line {line_number}."
            else:
                return f"Error: Cannot insert into non-existent file: {path}"
        
        elif operation == 'replace':
            if file_exists:
                new_content = re.sub(pattern, content, current_content)
                if new_content == current_content:
                    return f"Pattern '{pattern}' not found in file. No changes would be made."
                preview = f"Will replace pattern '{pattern}' with new content."
            else:
                return f"Error: Cannot replace in non-existent file: {path}"
        
        elif operation == 'delete':
            if file_exists:
                new_content = re.sub(pattern, '', current_content)
                if new_content == current_content:
                    return f"Pattern '{pattern}' not found in file. No changes would be made."
                preview = f"Will delete all occurrences of pattern '{pattern}'."
            else:
                return f"Error: Cannot delete from non-existent file: {path}"
                
        elif operation == 'delete_lines':
            if file_exists:
                lines = current_content.splitlines()
                
                # Validate line numbers
                if start_line < 1:
                    start_line = 1
                if end_line > len(lines):
                    end_line = len(lines)
                if start_line > end_line:
                    return f"Error: Start line ({start_line}) cannot be greater than end line ({end_line})"
                    
                # Remove the lines
                new_lines = lines[:start_line-1] + lines[end_line:]
                new_content = '\n'.join(new_lines)
                preview = f"Will delete lines {start_line}-{end_line} ({end_line - start_line + 1} lines)."
            else:
                return f"Error: Cannot delete lines from non-existent file: {path}"
        
        # If just previewing, return the diff
        if not confirm:
            preview_response = f"Preview of changes to {path} ({operation}):\n\n{preview}\n\n"
            
            if operation == 'write':
                preview_response += f"New content:\n```\n{content[:500]}"
                if len(content) > 500:
                    preview_response += "\n... (content truncated) ..."
                preview_response += "\n```"
            elif operation in ['replace', 'delete', 'append', 'insert', 'delete_lines']:
                diff = difflib.unified_diff(
                    current_content.splitlines(),
                    new_content.splitlines(),
                    fromfile=f"{path} (before)",
                    tofile=f"{path} (after)",
                    lineterm=''
                )
                diff_text = '\n'.join(diff)
                preview_response += f"Diff:\n```diff\n{diff_text}\n```"
            
            preview_response += "\n\nTo apply these changes, set confirm=True"
            return preview_response
        
        # Execute the edit
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the new content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        ctx.info(f"Successfully edited file: {path} ({operation})")
        return f"Successfully edited file: {path} ({operation})"
    
    except UnicodeDecodeError:
        return f"Error: File appears to be binary and cannot be edited as text: {path}"
    except PermissionError:
        return f"Error: Permission denied when editing file: {path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"

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
async def delete_path(path_to_delete: str, ctx: Context, confirm: bool = False) -> str:
    """
    Delete a file or directory within the project.
    
    Args:
        path_to_delete: Path to delete (relative to project root or absolute)
        confirm: Set to true to execute the deletion, false to preview only
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
    
    # Preview or execute based on confirm flag
    if not confirm:
        if path.is_dir():
            file_count = sum(1 for _ in path.glob('**/*') if _.is_file())
            dir_count = sum(1 for _ in path.glob('**/*') if _.is_dir())
            preview = f"Will delete directory: {path}\n"
            preview += f"This will remove {file_count} files and {dir_count} subdirectories."
        else:
            try:
                # Try to preview the file content
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                preview = f"Will delete file: {path}\n"
                preview += f"File size: {path.stat().st_size} bytes\n"
                preview += f"First 200 characters:\n```\n{content[:200]}" 
                if len(content) > 200:
                    preview += "..."
                preview += "\n```"
            except:
                preview = f"Will delete file: {path}\n"
                preview += f"File size: {path.stat().st_size} bytes (binary or non-readable file)"
                
        return f"{preview}\n\nTo confirm deletion, set confirm=True"
    
    # Execute the deletion
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