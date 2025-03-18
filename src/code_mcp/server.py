#!/usr/bin/env python3
"""
Code-MCP: Terminal and Code Integration for Claude AI

This script connects Claude AI to your development environment through 
the Model Context Protocol (MCP), enabling terminal commands and file operations.
"""

import os
import sys
import json
import shutil
import subprocess
import re
import difflib
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from mcp.server.fastmcp import FastMCP, Context, Image
import asyncio
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Import code editing utilities
from .edit_utils import (
    flexible_search_and_replace, generate_diff, 
    parse_search_replace_blocks, parse_unified_diff,
    apply_unified_diff, process_edit_blocks
)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CodeMCPServer")

# Function to determine the project root directory
def get_project_root():
    """Get the project root directory, defaulting to the current directory"""
    cwd_path = Path.cwd().absolute()
    logger.info(f"Using current directory as project root: {cwd_path}")
    return cwd_path
# Global variable to store the project root directory
PROJECT_ROOT = get_project_root()
logger.info(f"Initializing with project root: {PROJECT_ROOT}")

# Validate that the directory exists
if not PROJECT_ROOT.exists():
    logger.error(f"Error: Project directory {PROJECT_ROOT} does not exist")
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

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> None:
    """Manage server startup and shutdown lifecycle"""
    try:
        # Log that we're starting up
        logger.info("CodeMCP server starting up")
        logger.info(f"Project root: {PROJECT_ROOT}")
        
        # Return empty context
        yield {}
    finally:
        # Clean up on shutdown
        logger.info("CodeMCP server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "CodeMCP",
    description="Code and Terminal integration through the Model Context Protocol",
    lifespan=server_lifespan
)

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
def list_directory(dir_path: str = "") -> str:
    """
    List the contents of a directory within the project in a tree-like format.
    
    Args:
        dir_path: Path to the directory (relative to project root or absolute, empty for project root)
        max_depth: Maximum depth for the directory tree (default: 3)
    """
    max_depth = 10  # Set a default max depth for the tree
    
    path = Path(dir_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
        if dir_path == "":
            path = PROJECT_ROOT
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot access directory outside project directory: {path}"
    
    if not path.exists():
        return f"Error: Directory does not exist: {path}"
    
    if not path.is_dir():
        return f"Error: Path is not a directory: {path}"
    
    try:
        output = [f"Directory listing for {path}:"]
        output.append("")
        
        def generate_tree(directory: Path, prefix: str = "", is_last: bool = True, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                output.append(f"{prefix}{'└── ' if is_last else '├── '}...")
                return
                
            # Get items in the directory
            try:
                items = list(directory.iterdir())
                # Sort: directories first, then files, both alphabetically
                items.sort(key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                output.append(f"{prefix}{'└── ' if is_last else '├── '}[Permission denied]")
                return
                
            # Add empty line if we're at the root and have items
            if current_depth == 0 and items:
                pass  # We already have an empty line
                
            # Process each item
            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                
                # Display the item
                if current_depth == 0:
                    # At root level, use emojis and add size for files
                    if item.is_dir():
                        output.append(f"📁 {item.name}/")
                    else:
                        size_str = f" ({item.stat().st_size:,} bytes)"
                        output.append(f"📄 {item.name}{size_str}")
                else:
                    # For subdirectories, use tree structure
                    if item.is_dir():
                        output.append(f"{prefix}{'└── ' if is_last_item else '├── '}📁 {item.name}/")
                    else:
                        size_str = f" ({item.stat().st_size:,} bytes)"
                        output.append(f"{prefix}{'└── ' if is_last_item else '├── '}📄 {item.name}{size_str}")
                
                # Recursively process subdirectories
                if item.is_dir() and current_depth > 0:
                    new_prefix = prefix + ('    ' if is_last_item else '│   ')
                    generate_tree(item, new_prefix, True, current_depth + 1)
                elif item.is_dir() and current_depth == 0:
                    # First level directories get special treatment - show their contents indented
                    subdirectory_items = list(item.iterdir())
                    # Sort: directories first, then files, both alphabetically
                    subdirectory_items.sort(key=lambda x: (x.is_file(), x.name.lower()))
                    
                    # Only show up to 5 items at the first level to avoid overwhelming output
                    max_items = min(5, len(subdirectory_items))
                    has_more = len(subdirectory_items) > max_items
                    
                    for j, subitem in enumerate(subdirectory_items[:max_items]):
                        is_last_subitem = j == max_items - 1 and not has_more
                        
                        if subitem.is_dir():
                            output.append(f"    {'└── ' if is_last_subitem else '├── '}📁 {subitem.name}/")
                        else:
                            size_str = f" ({subitem.stat().st_size:,} bytes)"
                            output.append(f"    {'└── ' if is_last_subitem else '├── '}📄 {subitem.name}{size_str}")
                    
                    if has_more:
                        output.append(f"    └── ... ({len(subdirectory_items) - max_items} more items)")
                    
                    # Add a separator between top-level directories
                    if not is_last_item:
                        output.append("")
        
        # Generate the tree
        generate_tree(path)
        
        return "\n".join(output)
    
    except PermissionError:
        return f"Error: Permission denied when accessing directory: {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"
    
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
def run_command(ctx: Context, command: str) -> str:
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
        logger.info(f"Executing command: {command}")
        
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
def git_operation(ctx: Context, operation: str, confirm: bool = False) -> str:
    """
    Execute a git operation in the project repository.
    
    Args:
        operation: The git operation to perform (e.g., "status", "log", "branch")
        confirm: Set to true to execute operations that require confirmation (like push)
    """
    try:
        # Check if the project directory is a git repository
        repo_path = PROJECT_ROOT
        if not (repo_path / '.git').exists():
            return "Error: The project directory is not a git repository"
        
        # Highly dangerous operations that are always blocked
        highly_dangerous_operations = ["reset --hard", "clean -f"]
        if any(op in operation for op in highly_dangerous_operations):
            return f"Error: Potentially destructive git operation not allowed: {operation}"
        
        # Operations that require confirmation (like push)
        warning_operations = ["push"]
        requires_confirmation = any(op in operation for op in warning_operations)
        
        if requires_confirmation and not confirm:
            return f"""⚠️ Warning: The git operation '{operation}' can affect remote repositories and should be used with caution.
            
This operation could:
- Modify shared repositories that other developers are using
- Make local commits visible to others
- Potentially overwrite others' work if force-pushing

To confirm and execute this operation, set confirm=True"""
        
        # Log the operation
        logger.info(f"Executing git operation: {operation}")
        
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
def read_file(ctx: Context, file_path: str) -> str:
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
        
        logger.info(f"Successfully read file: {path}")
        return f"Contents of {path}:\n\n```\n{content}\n```"
    
    except UnicodeDecodeError:
        return f"Error: File appears to be binary and cannot be displayed as text: {path}"
    except PermissionError:
        return f"Error: Permission denied when reading file: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

# Tool for editing files with various operations
@mcp.tool()
def edit_file(
    ctx: Context, 
    file_path: str, 
    operation: str, 
    content: str = "", 
    line_number: int = None, 
    pattern: str = None, 
    start_line: int = None, 
    end_line: int = None, 
    confirm: bool = False
) -> str:
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
        
        logger.info(f"Successfully edited file: {path} ({operation})")
        return f"Successfully edited file: {path} ({operation})"
    
    except UnicodeDecodeError:
        return f"Error: File appears to be binary and cannot be edited as text: {path}"
    except PermissionError:
        return f"Error: Permission denied when editing file: {path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"

# Helper functions for smart_edit
def find_function_in_file(content: str, function_name: str) -> Optional[Tuple[int, int, str]]:
    """
    Find a function definition in file content.
    
    Args:
        content: File content to search
        function_name: Name of the function to find
        
    Returns:
        Tuple of (start_line, end_line, function_content) or None if not found
    """
    lines = content.splitlines()
    
    # Find the start of the function
    func_pattern = fr"^\s*def\s+{re.escape(function_name)}\s*\("
    func_start = None
    
    for i, line in enumerate(lines):
        if re.match(func_pattern, line):
            func_start = i
            break
    
    if func_start is None:
        return None
    
    # Find the end of the function by tracking indentation
    base_indent = len(lines[func_start]) - len(lines[func_start].lstrip())
    func_end = func_start
    
    in_docstring = False
    docstring_delimiter = None
    
    for i in range(func_start + 1, len(lines)):
        # Skip empty lines
        if not lines[i].strip():
            func_end = i
            continue
        
        # Check for docstring delimiters
        line = lines[i].strip()
        if not in_docstring and (line.startswith('"""') or line.startswith("'''")):
            in_docstring = True
            docstring_delimiter = line[:3]
            
            # Handle single-line docstrings
            if line.endswith(docstring_delimiter) and len(line) > 3:
                in_docstring = False
                func_end = i
                continue
        
        elif in_docstring and docstring_delimiter:
            if line.endswith(docstring_delimiter):
                in_docstring = False
            func_end = i
            continue
        
        # If we find a line with same or less indentation, we've left the function
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if not in_docstring and curr_indent <= base_indent:
            break
        
        func_end = i
    
    # Extract the function content
    func_content = '\n'.join(lines[func_start:func_end + 1])
    
    return func_start, func_end, func_content


def find_pattern_in_file(
    content: str, 
    pattern: str, 
    regex_mode: bool = False, 
    fuzzy_match: bool = False
) -> Union[Tuple[int, List[Tuple[int, str]]], str, None]:
    """
    Find a pattern in file content.
    
    Args:
        content: File content to search
        pattern: Pattern to find
        regex_mode: Use regex for pattern matching
        fuzzy_match: Use fuzzy matching for more flexible matches
        
    Returns:
        Tuple of (match_count, list of (line_no, excerpt)) or None if not found or error message
    """
    lines = content.splitlines()
    
    try:
        if regex_mode:
            # Use regex search
            matches = list(re.finditer(pattern, content))
        elif fuzzy_match:
            # Use difflib for fuzzy matching
            from difflib import SequenceMatcher
            matches = []
            
            # Check each potential line and nearby context
            context_size = min(len(pattern) // 2, 20)
            
            for i, line in enumerate(lines):
                # Skip tiny lines
                if len(line.strip()) < 5:
                    continue
                
                # Check the line and surrounding context
                start_idx = max(0, i - context_size)
                end_idx = min(len(lines), i + context_size + 1)
                
                chunk = '\n'.join(lines[start_idx:end_idx])
                
                # Check similarity
                s = SequenceMatcher(None, pattern, chunk)
                if s.ratio() > 0.7:  # Threshold for similarity
                    # Find the best matching block
                    match = s.find_longest_match(0, len(pattern), 0, len(chunk))
                    
                    if match.size > min(10, len(pattern) // 2):
                        # This is a decent match
                        # Convert chunk position to content position
                        chunk_start = sum(len(line) + 1 for line in lines[:start_idx])
                        matches.append(type('obj', (object,), {
                            'start': lambda: chunk_start + match.b,
                            'end': lambda: chunk_start + match.b + match.size,
                            'group': lambda: chunk[match.b:match.b + match.size]
                        }))
        else:
            # Use standard search
            matches = list(re.finditer(re.escape(pattern), content))
        
        if not matches:
            return None
        
        # Process matches
        match_locations = []
        for match in matches:
            # Find line number
            start_pos = match.start()
            line_no = content[:start_pos].count('\n') + 1
            
            # Get match with context
            context_start = max(0, start_pos - 40)
            context_end = min(len(content), match.end() + 40)
            
            # Get the line start and end
            line_start = content.rfind('\n', 0, start_pos) + 1
            line_end = content.find('\n', start_pos)
            if line_end == -1:
                line_end = len(content)
            
            # Extract context
            before = content[context_start:start_pos]
            matched = content[start_pos:match.end()]
            after = content[match.end():context_end]
            
            excerpt = f"...{before}[MATCH: {matched}]{after}..."
            
            match_locations.append((line_no, excerpt))
        
        return len(matches), match_locations
    
    except re.error as e:
        return f"Invalid regex pattern: {str(e)}"
    except Exception as e:
        return f"Error finding pattern: {str(e)}"


def suggest_similar_patterns(content: str, pattern: str) -> List[Tuple[int, str]]:
    """
    Suggest similar patterns in the content.
    
    Args:
        content: File content to search
        pattern: Pattern that wasn't found
        
    Returns:
        List of (line_no, line_text) for similar lines
    """
    # Extract significant words from the pattern
    words = re.findall(r'\w+', pattern)
    significant_words = [word for word in words if len(word) >= 4]
    
    if not significant_words:
        significant_words = [word for word in words if len(word) >= 2]
    
    if not significant_words:
        return []
    
    # Look for lines containing these words
    lines = content.splitlines()
    matches = []
    
    for i, line in enumerate(lines):
        for word in significant_words:
            if word.lower() in line.lower():
                matches.append((i + 1, line.strip()))
                break
    
    # Sort by relevance (number of matching words)
    def match_score(line_info):
        line_no, text = line_info
        score = sum(1 for word in significant_words if word.lower() in text.lower())
        return score
    
    matches.sort(key=match_score, reverse=True)
    
    return matches[:10]  # Return top 10 matches

@mcp.tool()
def smart_edit(
    ctx: Context,
    file_path: str, 
    operation: str = "preview",
    function_name: str = None, 
    pattern: str = None, 
    new_content: str = None,
    regex_mode: bool = False, 
    context_lines: int = 3, 
    confirm: bool = False,
    edit_format: str = None,
    fuzzy_match: bool = False,
    match_indent: bool = True
) -> str:
    """
    Enhanced file editing with smart pattern matching and function-level operations.
    
    Args:
        file_path: Path to the file (relative to project root or absolute)
        operation: Type of edit ('preview', 'update_function', 'replace', 'delete', 'append', 'write', 'edit_block')
        function_name: Target function name for function-level operations
        pattern: Pattern to find (with flexible whitespace matching)
        new_content: New content to insert/replace
        regex_mode: Enable regex pattern matching
        context_lines: Number of context lines to show in previews
        confirm: Set to true to execute the edit, false to preview only
        edit_format: Format for edits ('search_replace', 'unified_diff', 'whole_file') when using edit_block operation
        fuzzy_match: Enable fuzzy matching for more flexible pattern matching
        match_indent: Account for indentation differences when matching patterns
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot access file outside project directory: {path}"
    
    # Handle file existence check based on operation
    file_exists = path.exists() and path.is_file()
    if not file_exists and operation not in ["preview", "append", "write", "edit_block"]:
        return f"Error: File does not exist: {path}"
    
    try:
        # Read the file content if it exists
        current_content = ""
        if file_exists:
            with open(path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        
        # OPERATION: PREVIEW
        if operation == "preview":
            info = []
            
            # File info
            info.append(f"File: {path}")
            if file_exists:
                info.append(f"Size: {path.stat().st_size} bytes")
                info.append(f"Lines: {len(current_content.splitlines())}")
                
                # Count Python functions and classes if it's a Python file
                if path.suffix.lower() == '.py':
                    func_count = sum(1 for line in current_content.splitlines() 
                                    if re.match(r'^\s*def\s+\w+\s*\(', line))
                    class_count = sum(1 for line in current_content.splitlines() 
                                     if re.match(r'^\s*class\s+\w+', line))
                    info.append(f"Functions: {func_count}")
                    info.append(f"Classes: {class_count}")
            else:
                info.append("File does not exist yet.")
            
            # Function preview
            if function_name and file_exists:
                func_info = find_function_in_file(current_content, function_name)
                if func_info:
                    start_line, end_line, func_content = func_info
                    info.append(f"\nFunction '{function_name}' found at lines {start_line+1}-{end_line+1}:")
                    info.append(f"```python\n{func_content}\n```")
                else:
                    info.append(f"\nFunction '{function_name}' not found in the file.")
            
            # Pattern preview
            if pattern and file_exists:
                pattern_info = find_pattern_in_file(current_content, pattern, regex_mode, fuzzy_match)
                if isinstance(pattern_info, str):  # Error occurred
                    info.append(f"\nError finding pattern: {pattern_info}")
                elif pattern_info:
                    match_count, match_locations = pattern_info
                    info.append(f"\nPattern '{pattern}' found {match_count} times:")
                    
                    for i, (line_no, excerpt) in enumerate(match_locations[:3]):
                        info.append(f"Match {i+1} at line {line_no}:")
                        info.append(f"```\n{excerpt}\n```")
                    
                    if match_count > 3:
                        info.append(f"(and {match_count - 3} more matches)")
                else:
                    info.append(f"\nPattern '{pattern}' not found in the file.")
                    
                    # Suggest similar matches
                    suggestions = suggest_similar_patterns(current_content, pattern)
                    if suggestions:
                        info.append("\nPossible similar patterns:")
                        for i, (line_no, text) in enumerate(suggestions[:5]):
                            info.append(f"Line {line_no}: {text}")
            
            return "\n".join(info)
        
        # OPERATION: EDIT_BLOCK - Process content as edit blocks
        elif operation == "edit_block":
            if not new_content:
                return "Error: New content is required for the edit_block operation"
            
            if not file_exists:
                # Handle creating a new file
                parent_dir = path.parent
                if not parent_dir.exists():
                    parent_dir.mkdir(parents=True, exist_ok=True)
                
                if not confirm:
                    return f"Will create new file: {path}\n\nContent preview:\n```\n{new_content[:200]}{'...' if len(new_content) > 200 else ''}\n```\n\nTo execute this change, set confirm=True"
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                logger.info(f"Created new file: {path}")
                return f"Successfully created new file: {path}"
            
            # Determine edit format
            format_type = edit_format or "auto"
            
            if format_type == "auto":
                # Try to detect the format
                if "<<<<<<< SEARCH" in new_content:
                    format_type = "search_replace"
                elif new_content.startswith("---") and "+++ " in new_content:
                    format_type = "unified_diff"
                else:
                    format_type = "whole_file"
            
            # Process based on format type
            if format_type == "search_replace":
                blocks = parse_search_replace_blocks(new_content)
                if not blocks:
                    return "Error: No valid search/replace blocks found in the content"
                
                # For simplicity, just use the first block
                _, search_text, replace_text = blocks[0]
                
                updated_content = flexible_search_and_replace(search_text, replace_text, current_content)
                if not updated_content:
                    return f"Error: Could not find pattern to replace in {path}"
            
            elif format_type == "unified_diff":
                diff_blocks = parse_unified_diff(new_content)
                if not diff_blocks:
                    return "Error: No valid unified diff blocks found in the content"
                
                # For simplicity, just use the first diff
                _, diff_lines = diff_blocks[0]
                
                updated_content = apply_unified_diff(current_content, diff_lines)
                if not updated_content:
                    return f"Error: Failed to apply diff to {path}"
            
            elif format_type == "whole_file":
                updated_content = new_content
            
            else:
                return f"Error: Unsupported edit format: {format_type}"
            
            # Generate diff for preview
            diff = generate_diff(current_content, updated_content, str(path), context_lines)
            
            if not confirm:
                return f"Preview of changes to {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            
            # Apply the changes
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            logger.info(f"Successfully updated file: {path}")
            return f"Successfully updated file: {path}"
        
        # OPERATION: UPDATE_FUNCTION - Update a specific function in the file
        elif operation == "update_function":
            if not function_name:
                return "Error: Function name is required for update_function operation"
                
            if not new_content:
                return "Error: New content is required for update_function operation"
            
            func_info = find_function_in_file(current_content, function_name)
            if not func_info:
                return f"Error: Function '{function_name}' not found in {path}"
            
            start_line, end_line, func_content = func_info
            
            # Replace the function
            lines = current_content.splitlines()
            new_lines = lines[:start_line] + new_content.splitlines() + lines[end_line+1:]
            updated_content = '\n'.join(new_lines)
            
            # Generate diff for preview
            diff = generate_diff(current_content, updated_content, str(path), context_lines)
            
            if not confirm:
                return f"Preview of function update in {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            
            # Apply the changes
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            logger.info(f"Successfully updated function '{function_name}' in {path}")
            return f"Successfully updated function '{function_name}' in {path}"
        
        # OPERATION: REPLACE - Replace pattern with new content
        elif operation == "replace":
            if not pattern:
                return "Error: Pattern is required for replace operation"
                
            if new_content is None:  # Allow empty string replacement
                return "Error: New content parameter is required for replace operation"
            
            # Find the pattern
            pattern_info = find_pattern_in_file(current_content, pattern, regex_mode, fuzzy_match)
            
            if isinstance(pattern_info, str):  # Error occurred
                return f"Error finding pattern: {pattern_info}"
                
            if not pattern_info:
                # Try to suggest similar patterns
                suggestions = suggest_similar_patterns(current_content, pattern)
                suggestion_text = ""
                
                if suggestions:
                    suggestion_text = "\n\nPossible similar patterns that might match:"
                    for i, (line_no, text) in enumerate(suggestions[:5]):
                        suggestion_text += f"\nLine {line_no}: {text}"
                
                return f"Pattern '{pattern}' not found in {path}.{suggestion_text}"
            
            # Use our enhanced search and replace
            if regex_mode:
                try:
                    updated_content = re.sub(pattern, new_content, current_content)
                except re.error as e:
                    return f"Error in regex pattern: {str(e)}"
            else:
                updated_content = flexible_search_and_replace(pattern, new_content, current_content)
                
                if not updated_content:
                    return f"Failed to replace pattern '{pattern}' in {path}"
            
            # Generate diff for preview
            diff = generate_diff(current_content, updated_content, str(path), context_lines)
            
            if not confirm:
                return f"Preview of pattern replacement in {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            
            # Apply the changes
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            logger.info(f"Successfully replaced pattern in {path}")
            return f"Successfully replaced pattern in {path}"
        
        # OPERATION: WRITE - Completely overwrite the file
        elif operation == "write":
            if new_content is None:
                return "Error: New content is required for write operation"
            
            if file_exists:
                # Preview with diff
                diff = generate_diff(current_content, new_content, str(path), context_lines)
                
                if not confirm:
                    return f"Preview of complete file replacement for {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            else:
                # Preview for new file
                preview = f"Will create new file: {path}"
                
                if not confirm:
                    return f"{preview}\n\nContent preview:\n```\n{new_content[:200]}{'...' if len(new_content) > 200 else ''}\n```\n\nTo execute this change, set confirm=True"
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            action = "updated" if file_exists else "created"
            logger.info(f"Successfully {action} file: {path}")
            return f"Successfully {action} file: {path}"
        
        # OPERATION: APPEND - Add content to the end of the file
        elif operation == "append":
            if new_content is None:
                return "Error: New content is required for append operation"
            
            updated_content = current_content
            if updated_content and not updated_content.endswith("\n"):
                updated_content += "\n"
            updated_content += new_content
            
            if file_exists:
                # Preview with diff
                diff = generate_diff(current_content, updated_content, str(path), context_lines)
                
                if not confirm:
                    return f"Preview of content append for {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            else:
                # Preview for new file
                preview = f"Will create new file: {path}"
                
                if not confirm:
                    return f"{preview}\n\nContent preview:\n```\n{new_content[:200]}{'...' if len(new_content) > 200 else ''}\n```\n\nTo execute this change, set confirm=True"
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            action = "appended to" if file_exists else "created"
            logger.info(f"Successfully {action} file: {path}")
            return f"Successfully {action} file: {path}"
        
        # OPERATION: DELETE - Remove content matching a pattern
        elif operation == "delete":
            if not pattern:
                return "Error: Pattern is required for delete operation"
            
            # Find the pattern
            pattern_info = find_pattern_in_file(current_content, pattern, regex_mode, fuzzy_match)
            
            if isinstance(pattern_info, str):  # Error occurred
                return f"Error finding pattern: {pattern_info}"
                
            if not pattern_info:
                return f"Pattern '{pattern}' not found in {path}"
            
            # Delete the pattern
            if regex_mode:
                try:
                    updated_content = re.sub(pattern, '', current_content)
                except re.error as e:
                    return f"Error in regex pattern: {str(e)}"
            else:
                updated_content = flexible_search_and_replace(pattern, '', current_content)
                
                if not updated_content:
                    return f"Failed to delete pattern '{pattern}' in {path}"
            
            # Generate diff for preview
            diff = generate_diff(current_content, updated_content, str(path), context_lines)
            
            if not confirm:
                return f"Preview of pattern deletion in {path}:\n\n```diff\n{diff}\n```\n\nTo apply these changes, set confirm=True"
            
            # Apply the changes
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            logger.info(f"Successfully deleted pattern in {path}")
            return f"Successfully deleted pattern in {path}"
        
        else:
            return f"Error: Unsupported operation '{operation}'. Must be one of: preview, update_function, replace, delete, append, write, edit_block"
    
    except UnicodeDecodeError:
        return f"Error: File appears to be binary and cannot be edited as text: {path}"
    except PermissionError:
        return f"Error: Permission denied when accessing file: {path}"
    except Exception as e:
        return f"Error processing file: {str(e)}"

@mcp.tool()
def edit_block(
    ctx: Context,
    edit_content: str,
    confirm: bool = False
) -> str:
    """
    Process edit blocks to modify code across multiple files.
    
    This tool parses the provided edit_content for search/replace blocks 
    or unified diff format changes and applies them to the appropriate files.
    
    Args:
        edit_content: Text containing edit blocks in either search/replace or unified diff format
        confirm: Set to true to execute the edits, false to preview only
    """
    # Detect the edit format
    format_type = "unknown"
    if "<<<<<<< SEARCH" in edit_content:
        format_type = "search_replace"
    elif edit_content.startswith("---") and "+++ " in edit_content:
        format_type = "unified_diff"
    
    if format_type == "unknown":
        return "Error: Could not detect a valid edit format in the provided content. Please use either search/replace blocks or unified diff format."
    
    # Process edits based on format
    file_edits = {}
    
    if format_type == "search_replace":
        # Parse search/replace blocks
        blocks = parse_search_replace_blocks(edit_content)
        
        if not blocks:
            return "Error: No valid search/replace blocks found in the content"
        
        # Process each block
        for filename, search_text, replace_text in blocks:
            path = Path(filename)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            
            # Security check
            if not is_safe_path(path):
                return f"Error: Cannot access file outside project directory: {path}"
            
            # Read the current content
            current_content = ""
            if path.exists() and path.is_file():
                with open(path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            elif not search_text.strip():
                # Creating a new file - this is allowed
                pass
            else:
                return f"Error: Cannot find file {path} to edit"
            
            # Apply the search/replace
            if not search_text.strip() and not path.exists():
                # Creating a new file
                new_content = replace_text
            else:
                new_content = flexible_search_and_replace(search_text, replace_text, current_content)
                
                if not new_content:
                    return f"Error: Failed to find pattern to replace in {path}"
            
            file_edits[str(path)] = (current_content, new_content)
    
    elif format_type == "unified_diff":
        # Parse unified diff blocks
        diff_blocks = parse_unified_diff(edit_content)
        
        if not diff_blocks:
            return "Error: No valid unified diff blocks found in the content"
        
        # Process each diff
        for filename, diff_lines in diff_blocks:
            path = Path(filename)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            
            # Security check
            if not is_safe_path(path):
                return f"Error: Cannot access file outside project directory: {path}"
            
            # Read the current content or create a new file
            current_content = ""
            if path.exists() and path.is_file():
                with open(path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            elif filename.startswith("/dev/null"):
                # Creating a new file - this is allowed in unified diff format
                pass
            else:
                return f"Error: Cannot find file {path} to edit"
            
            # Apply the diff
            new_content = apply_unified_diff(current_content, diff_lines)
            if not new_content and current_content:
                return f"Error: Failed to apply diff to {path}"
            
            file_edits[str(path)] = (current_content, new_content)
    
    # Preview or execute
    if not confirm:
        preview = [f"Preview of edit block changes ({format_type} format):"]
        
        for path, (current, new) in file_edits.items():
            path_obj = Path(path)
            
            if not path_obj.exists():
                preview.append(f"\n## Creating new file: {path}")
                preview.append(f"```\n{new[:500]}{'...' if len(new) > 500 else ''}\n```")
            else:
                diff = generate_diff(current, new, path)
                preview.append(f"\n## Changes to {path}:")
                preview.append(f"```diff\n{diff}\n```")
        
        preview.append("\nTo apply these changes, set confirm=True")
        return "\n".join(preview)
    
    # Execute the changes
    results = []
    
    for path, (current, new) in file_edits.items():
        path_obj = Path(path)
        
        # Create directories if needed
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path_obj, 'w', encoding='utf-8') as f:
            f.write(new)
        
        action = "Updated" if path_obj.exists() else "Created"
        results.append(f"{action} file: {path}")
        logger.info(f"{action} file: {path} using edit block")
    
    return "Successfully applied edit block changes:\n- " + "\n- ".join(results)

# Tool for creating directories
@mcp.tool()
def create_directory(ctx: Context, dir_path: str) -> str:
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
        logger.info(f"Created directory: {path}")
        
        return f"Successfully created directory: {path}"
    
    except PermissionError:
        return f"Error: Permission denied when creating directory: {path}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"

# Tool for deleting files or directories
@mcp.tool()
def delete_path(ctx: Context, path_to_delete: str, confirm: bool = False) -> str:
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
            logger.info(f"Successfully deleted directory: {path}")
            return f"Successfully deleted directory: {path}"
        else:
            # Delete file
            path.unlink()
            logger.info(f"Successfully deleted file: {path}")
            return f"Successfully deleted file: {path}"
    
    except PermissionError:
        return f"Error: Permission denied when deleting: {path}"
    except Exception as e:
        return f"Error deleting path: {str(e)}"

@mcp.tool()
def list_directory(ctx: Context, dir_path: str = "", max_depth: int = 10) -> str:
    """
    List the contents of a directory within the project in a tree-like format.
    
    Args:
        dir_path: Path to the directory (relative to project root or absolute, empty for project root)
        max_depth: Maximum depth for the directory tree (default: 3)
    """
    path = Path(dir_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
        if dir_path == "":
            path = PROJECT_ROOT
    
    # Security check
    if not is_safe_path(path):
        return f"Error: Cannot access directory outside project directory: {path}"
    
    if not path.exists():
        return f"Error: Directory does not exist: {path}"
    
    if not path.is_dir():
        return f"Error: Path is not a directory: {path}"
    
    try:
        output = [f"Directory listing for {path}:"]
        output.append("")
        
        def generate_tree(directory: Path, prefix: str = "", is_last: bool = True, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                output.append(f"{prefix}{'└── ' if is_last else '├── '}...")
                return
                
            # Get items in the directory
            try:
                items = list(directory.iterdir())
                # Sort: directories first, then files, both alphabetically
                items.sort(key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                output.append(f"{prefix}{'└── ' if is_last else '├── '}[Permission denied]")
                return
                
            # Add empty line if we're at the root and have items
            if current_depth == 0 and items:
                pass  # We already have an empty line
                
            # Process each item
            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                
                # Display the item
                if current_depth == 0:
                    # At root level, use emojis and add size for files
                    if item.is_dir():
                        output.append(f"📁 {item.name}/")
                    else:
                        size_str = f" ({item.stat().st_size:,} bytes)"
                        output.append(f"📄 {item.name}{size_str}")
                else:
                    # For subdirectories, use tree structure
                    if item.is_dir():
                        output.append(f"{prefix}{'└── ' if is_last_item else '├── '}📁 {item.name}/")
                    else:
                        size_str = f" ({item.stat().st_size:,} bytes)"
                        output.append(f"{prefix}{'└── ' if is_last_item else '├── '}📄 {item.name}{size_str}")
                
                # Recursively process subdirectories
                if item.is_dir() and current_depth > 0:
                    new_prefix = prefix + ('    ' if is_last_item else '│   ')
                    generate_tree(item, new_prefix, True, current_depth + 1)
                elif item.is_dir() and current_depth == 0:
                    # First level directories get special treatment - show their contents indented
                    subdirectory_items = list(item.iterdir())
                    # Sort: directories first, then files, both alphabetically
                    subdirectory_items.sort(key=lambda x: (x.is_file(), x.name.lower()))
                    
                    # Only show up to 5 items at the first level to avoid overwhelming output
                    max_items = min(5, len(subdirectory_items))
                    has_more = len(subdirectory_items) > max_items
                    
                    for j, subitem in enumerate(subdirectory_items[:max_items]):
                        is_last_subitem = j == max_items - 1 and not has_more
                        
                        if subitem.is_dir():
                            output.append(f"    {'└── ' if is_last_subitem else '├── '}📁 {subitem.name}/")
                        else:
                            size_str = f" ({subitem.stat().st_size:,} bytes)"
                            output.append(f"    {'└── ' if is_last_subitem else '├── '}📄 {subitem.name}{size_str}")
                    
                    if has_more:
                        output.append(f"    └── ... ({len(subdirectory_items) - max_items} more items)")
                    
                    # Add a separator between top-level directories
                    if not is_last_item:
                        output.append("")
        
        # Generate the tree
        generate_tree(path)
        
        return "\n".join(output)
    
    except PermissionError:
        return f"Error: Permission denied when accessing directory: {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@mcp.prompt()
def code_operations_strategy() -> str:
    """Defines the preferred strategy for working with code files"""
    return """When working with code files and terminal commands:

1. First explore the project structure using list_directory().

2. Use read_file() to examine important files like:
   - README.md for project overview
   - package.json/pyproject.toml/requirements.txt for dependencies
   - Main source files for the implementation details

3. For terminal commands:
   - Use run_command() for general terminal operations
   - Use git_operation() for git-specific commands 

4. When editing files:
   - Use edit_file() for simple edits
   - Use smart_edit() for more complex operations like updating functions
   - Always use confirm=True when ready to make actual changes

5. For batch operations across multiple files:
   - Use edit_block() with a well-formatted block of changes

6. Always follow these best practices:
   - Before making changes, understand the project structure
   - Check if a file exists before trying to edit it
   - After making changes, verify their effect with appropriate commands
   - Use git_operation("status") to see what files changed
   
7. Be careful with:
   - Deleting files or directories (always use confirm=True)
   - Making changes to critical system files
   - Using destructive git commands (reset, clean)
"""

def main():
    """Run the MCP server"""
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="Code-MCP: Terminal and Code Integration for Claude AI")
    parser.add_argument("project_root", nargs="?", default=None, 
                        help="Path to the project root directory. Defaults to current directory if not provided.")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle version flag
    if args.version:
        import code_mcp
        print(f"Code-MCP version {code_mcp.__version__}")
        return 0
    
    # Set the project root global variable
    global PROJECT_ROOT
    if args.project_root:
        PROJECT_ROOT = Path(args.project_root).absolute()
        print(f"Using provided project root: {PROJECT_ROOT}")
    else:
        PROJECT_ROOT = Path.cwd().absolute()
        print(f"No project root provided, using current directory: {PROJECT_ROOT}")
    
    # Validate project root
    if not PROJECT_ROOT.is_dir():
        print(f"Error: Project root directory does not exist: {PROJECT_ROOT}")
        return 1
    
    # Start the MCP server
    print(f"Starting CodeMCP server with project root: {PROJECT_ROOT}")
    mcp.run()
    return 0
if __name__ == "__main__":
    main()