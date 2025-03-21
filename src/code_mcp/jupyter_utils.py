"""
Jupyter notebook utilities for the Code-MCP package.

This module provides functions for working with and manipulating Jupyter notebooks (.ipynb files).
"""

import json
import logging
import os
import subprocess
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import re

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("JupyterUtils")

def read_notebook(file_path: Path) -> Dict:
    """
    Read a Jupyter notebook file into a dictionary.
    
    Args:
        file_path: Path to the notebook file
        
    Returns:
        Dictionary containing notebook data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            nb_content = json.load(f)
        return nb_content
    except json.JSONDecodeError:
        logger.error(f"Error parsing notebook: {file_path}")
        raise ValueError(f"Invalid JSON in notebook file: {file_path}")
    except Exception as e:
        logger.error(f"Error reading notebook: {file_path}, {str(e)}")
        raise

def save_notebook(notebook: Dict, file_path: Path) -> None:
    """
    Save a notebook dictionary to a file.
    
    Args:
        notebook: Notebook dictionary
        file_path: Path to save the notebook to
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1)
    except Exception as e:
        logger.error(f"Error saving notebook to {file_path}: {str(e)}")
        raise

def get_notebook_metadata(notebook: Dict) -> Dict:
    """
    Extract metadata from a notebook.
    
    Args:
        notebook: Notebook dictionary
        
    Returns:
        Dictionary containing metadata
    """
    return notebook.get('metadata', {})

def get_notebook_cells(notebook: Dict) -> List[Dict]:
    """
    Get all cells from a notebook.
    
    Args:
        notebook: Notebook dictionary
        
    Returns:
        List of cell dictionaries
    """
    return notebook.get('cells', [])

def get_cell_by_index(notebook: Dict, index: int) -> Optional[Dict]:
    """
    Get a cell by its index.
    
    Args:
        notebook: Notebook dictionary
        index: Cell index (0-based)
        
    Returns:
        Cell dictionary if found, None otherwise
    """
    cells = get_notebook_cells(notebook)
    if 0 <= index < len(cells):
        return cells[index]
    return None

def extract_cell_content(cell: Dict, include_outputs: bool = False) -> str:
    """
    Extract content from a cell.
    
    Args:
        cell: Cell dictionary
        include_outputs: Whether to include outputs
        
    Returns:
        String containing cell content
    """
    result = ""
    
    # Add source content
    if 'source' in cell:
        if isinstance(cell['source'], list):
            result += "".join(cell['source'])
        else:
            result += str(cell['source'])
    
    # Add outputs if requested
    if include_outputs and 'outputs' in cell:
        for output in cell['outputs']:
            if output.get('output_type') == 'stream':
                if 'text' in output:
                    if isinstance(output['text'], list):
                        result += "\n# Output:\n" + "".join(output['text'])
                    else:
                        result += "\n# Output:\n" + str(output['text'])
            elif output.get('output_type') == 'execute_result':
                if 'data' in output and 'text/plain' in output['data']:
                    text = output['data']['text/plain']
                    if isinstance(text, list):
                        result += "\n# Result:\n" + "".join(text)
                    else:
                        result += "\n# Result:\n" + str(text)
    
    return result

def get_cell_type(cell: Dict) -> str:
    """
    Get the cell type.
    
    Args:
        cell: Cell dictionary
        
    Returns:
        Cell type string (e.g., 'code', 'markdown')
    """
    return cell.get('cell_type', 'code')

def create_cell(cell_type: str, content: str) -> Dict:
    """
    Create a new cell dictionary.
    
    Args:
        cell_type: Cell type ('code', 'markdown', 'raw')
        content: Cell content
        
    Returns:
        New cell dictionary
    """
    # Split content into lines
    if isinstance(content, str):
        source = content.splitlines(True)  # Keep the line endings
    else:
        source = [content]
    
    cell = {
        'cell_type': cell_type,
        'source': source,
        'metadata': {}
    }
    
    # Add outputs list for code cells
    if cell_type == 'code':
        cell['outputs'] = []
        cell['execution_count'] = None
    
    return cell

def add_cell(notebook: Dict, cell_type: str, content: str, position: int = -1) -> Dict:
    """
    Add a new cell to the notebook.
    
    Args:
        notebook: Notebook dictionary
        cell_type: Cell type ('code', 'markdown', 'raw')
        content: Cell content
        position: Position to insert the cell (-1 for end of notebook)
        
    Returns:
        Updated notebook dictionary
    """
    new_cell = create_cell(cell_type, content)
    
    # Make a deep copy of the notebook to avoid modifying the original
    import copy
    notebook_copy = copy.deepcopy(notebook)
    
    # Get cells from the notebook, create if doesn't exist
    if 'cells' not in notebook_copy:
        notebook_copy['cells'] = []
    
    cells = notebook_copy['cells']
    
    # Add the cell at the specified position
    if position < 0 or position >= len(cells):
        cells.append(new_cell)
    else:
        cells.insert(position, new_cell)
    
    return notebook_copy

def delete_cell(notebook: Dict, index: int) -> Dict:
    """
    Delete a cell from the notebook.
    
    Args:
        notebook: Notebook dictionary
        index: Cell index to delete
        
    Returns:
        Updated notebook dictionary
    """
    # Make a deep copy of the notebook
    import copy
    notebook_copy = copy.deepcopy(notebook)
    
    # Get cells from the notebook
    cells = notebook_copy.get('cells', [])
    
    # Check if index is valid
    if 0 <= index < len(cells):
        # Remove the cell
        cells.pop(index)
    else:
        logger.warning(f"Cell index {index} out of range [0, {len(cells)-1}]")
    
    return notebook_copy

def modify_cell(notebook: Dict, index: int, new_content: str = None, 
                cell_type: str = None) -> Dict:
    """
    Modify an existing cell in the notebook.
    
    Args:
        notebook: Notebook dictionary
        index: Cell index to modify
        new_content: New cell content (None to keep original)
        cell_type: New cell type (None to keep original)
        
    Returns:
        Updated notebook dictionary
    """
    # Make a deep copy of the notebook
    import copy
    notebook_copy = copy.deepcopy(notebook)
    
    # Get cells from the notebook
    cells = notebook_copy.get('cells', [])
    
    # Check if index is valid
    if 0 <= index < len(cells):
        cell = cells[index]
        
        # Update content if provided
        if new_content is not None:
            # Split content into lines
            if isinstance(new_content, str):
                cell['source'] = new_content.splitlines(True)  # Keep the line endings
            else:
                cell['source'] = [new_content]
        
        # Update cell type if provided
        if cell_type is not None:
            old_type = cell.get('cell_type', 'code')
            cell['cell_type'] = cell_type
            
            # Adjust cell structure based on type
            if cell_type == 'code' and old_type != 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
            elif cell_type != 'code' and old_type == 'code':
                # Remove code-specific fields
                if 'outputs' in cell:
                    del cell['outputs']
                if 'execution_count' in cell:
                    del cell['execution_count']
    else:
        logger.warning(f"Cell index {index} out of range [0, {len(cells)-1}]")
    
    return notebook_copy

def execute_notebook(notebook_path: Path, timeout: int = 300) -> Dict:
    """
    Execute a notebook and return the executed notebook.
    
    Args:
        notebook_path: Path to the notebook file
        timeout: Execution timeout in seconds
        
    Returns:
        Dictionary containing the executed notebook
    """
    try:
        # Check if nbconvert is available
        result = subprocess.run(['jupyter', 'nbconvert', '--version'], 
                               capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("jupyter nbconvert not found. Please install it with: pip install nbconvert")
            raise RuntimeError("jupyter nbconvert not found")
        
        # Create temporary output path
        output_path = notebook_path.with_suffix('.executed.ipynb')
        
        # Run the execution
        cmd = [
            'jupyter', 'nbconvert', 
            '--to', 'notebook', 
            '--execute', 
            f'--ExecutePreprocessor.timeout={timeout}',
            '--output', str(output_path.name),
            str(notebook_path)
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Error executing notebook: {process.stderr}")
            raise RuntimeError(f"Notebook execution failed: {process.stderr}")
        
        # Read the executed notebook
        executed_notebook = read_notebook(output_path)
        
        # Cleanup
        if output_path.exists():
            os.remove(output_path)
        
        return executed_notebook
    
    except FileNotFoundError:
        logger.error("jupyter command not found. Please install Jupyter: pip install jupyter")
        raise RuntimeError("jupyter command not found")
    except Exception as e:
        logger.error(f"Error executing notebook: {str(e)}")
        raise

def execute_cell(notebook: Dict, index: int) -> Dict:
    """
    Execute a single cell in the notebook.
    
    Note: This function saves the notebook to a temporary file, executes it, and returns the result.
    It's not possible to execute a single cell directly without using the Jupyter kernel.
    
    Args:
        notebook: Notebook dictionary
        index: Index of the cell to execute
        
    Returns:
        Updated notebook with executed cell
    """
    import tempfile
    
    # Check if the cell exists and is a code cell
    cell = get_cell_by_index(notebook, index)
    if cell is None:
        logger.error(f"Cell index {index} not found")
        return notebook
    
    if cell.get('cell_type') != 'code':
        logger.warning(f"Cell at index {index} is not a code cell")
        return notebook
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.ipynb', delete=False) as temp:
            temp_path = Path(temp.name)
        
        # Save the notebook to the temporary file
        save_notebook(notebook, temp_path)
        
        # Create a custom execute-single-cell notebook
        single_cell_notebook = {
            'cells': [cell],
            'metadata': notebook.get('metadata', {}),
            'nbformat': notebook.get('nbformat', 4),
            'nbformat_minor': notebook.get('nbformat_minor', 0)
        }
        
        single_cell_path = temp_path.with_suffix('.single.ipynb')
        save_notebook(single_cell_notebook, single_cell_path)
        
        # Execute the single-cell notebook
        executed_cell_notebook = execute_notebook(single_cell_path)
        
        # Get the executed cell
        if 'cells' in executed_cell_notebook and len(executed_cell_notebook['cells']) > 0:
            executed_cell = executed_cell_notebook['cells'][0]
            
            # Create a copy of the original notebook
            import copy
            updated_notebook = copy.deepcopy(notebook)
            
            # Replace the cell with the executed one
            updated_notebook['cells'][index] = executed_cell
            
            return updated_notebook
        
        # If execution failed, return the original notebook
        return notebook
    
    except Exception as e:
        logger.error(f"Error executing cell: {str(e)}")
        return notebook
    finally:
        # Clean up temporary files
        for path in [temp_path, single_cell_path]:
            if path.exists():
                try:
                    os.remove(path)
                except:
                    pass

def find_cells(notebook: Dict, pattern: str, case_sensitive: bool = False) -> List[int]:
    """
    Find cells matching a pattern.
    
    Args:
        notebook: Notebook dictionary
        pattern: Pattern to search for
        case_sensitive: Whether the search is case-sensitive
        
    Returns:
        List of cell indices matching the pattern
    """
    cells = get_notebook_cells(notebook)
    matches = []
    
    # Compile the regex
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)
    
    # Search each cell
    for i, cell in enumerate(cells):
        content = extract_cell_content(cell)
        if regex.search(content):
            matches.append(i)
    
    return matches

def convert_notebook(notebook_path: Path, output_format: str = 'html') -> Path:
    """
    Convert a notebook to another format.
    
    Args:
        notebook_path: Path to the notebook file
        output_format: Output format ('html', 'pdf', 'py', 'markdown', 'script')
        
    Returns:
        Path to the converted file
    """
    allowed_formats = ['html', 'pdf', 'python', 'markdown', 'script']
    format_map = {
        'py': 'python',
        'md': 'markdown',
        'js': 'script',
        'sh': 'script'
    }
    
    # Map format aliases
    if output_format in format_map:
        output_format = format_map[output_format]
    
    if output_format not in allowed_formats:
        logger.error(f"Unsupported output format: {output_format}. "
                    f"Supported formats: {', '.join(allowed_formats)}")
        raise ValueError(f"Unsupported output format: {output_format}")
    
    try:
        # Create output path
        output_path = notebook_path.with_suffix(f'.{output_format}')
        
        # Run the conversion
        cmd = [
            'jupyter', 'nbconvert', 
            f'--to={output_format}', 
            str(notebook_path),
            '--output', output_path.stem
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Error converting notebook: {process.stderr}")
            raise RuntimeError(f"Notebook conversion failed: {process.stderr}")
        
        # Handle the case where nbconvert uses a different extension
        if output_format == 'python':
            actual_output = notebook_path.with_suffix('.py')
            if actual_output.exists():
                output_path = actual_output
        elif output_format == 'markdown':
            actual_output = notebook_path.with_suffix('.md')
            if actual_output.exists():
                output_path = actual_output
        
        if not output_path.exists():
            logger.warning(f"Expected output file {output_path} not found!")
            # Try to find the correct output file
            parent_dir = notebook_path.parent
            matching_files = list(parent_dir.glob(f"{notebook_path.stem}.*"))
            # Find the most recently modified file
            if matching_files:
                output_path = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        return output_path
    
    except FileNotFoundError:
        logger.error("jupyter command not found. Please install Jupyter: pip install jupyter")
        raise RuntimeError("jupyter command not found")
    except Exception as e:
        logger.error(f"Error converting notebook: {str(e)}")
        raise

def get_notebook_summary(notebook: Dict) -> str:
    """
    Generate a summary of the notebook.
    
    Args:
        notebook: Notebook dictionary
        
    Returns:
        Summary string
    """
    cells = get_notebook_cells(notebook)
    metadata = get_notebook_metadata(notebook)
    
    # Count cell types
    code_cells = 0
    markdown_cells = 0
    raw_cells = 0
    
    for cell in cells:
        cell_type = get_cell_type(cell)
        if cell_type == 'code':
            code_cells += 1
        elif cell_type == 'markdown':
            markdown_cells += 1
        elif cell_type == 'raw':
            raw_cells += 1
    
    # Extract kernelspec info
    kernelspec = metadata.get('kernelspec', {})
    kernel_name = kernelspec.get('name', 'unknown')
    kernel_display_name = kernelspec.get('display_name', 'Unknown')
    
    # Build summary
    summary = f"Jupyter Notebook Summary:\n"
    summary += f"Total cells: {len(cells)}\n"
    summary += f"Code cells: {code_cells}\n"
    summary += f"Markdown cells: {markdown_cells}\n"
    summary += f"Raw cells: {raw_cells}\n"
    summary += f"Kernel: {kernel_display_name} ({kernel_name})\n"
    
    # Check for common notebook metadata
    if 'authors' in metadata:
        authors = metadata['authors']
        if isinstance(authors, list):
            authors_str = ', '.join(author.get('name', '') for author in authors)
            summary += f"Authors: {authors_str}\n"
    
    if 'title' in metadata:
        summary += f"Title: {metadata['title']}\n"
    
    return summary

def create_new_notebook(kernel_name: str = 'python3') -> Dict:
    """
    Create a new empty notebook.
    
    Args:
        kernel_name: Name of the kernel to use
        
    Returns:
        Dictionary containing the new notebook
    """
    # Create basic notebook structure
    notebook = {
        'cells': [],
        'metadata': {
            'kernelspec': {
                'display_name': 'Python 3',
                'language': 'python',
                'name': kernel_name
            },
            'language_info': {
                'codemirror_mode': {
                    'name': 'ipython',
                    'version': 3
                },
                'file_extension': '.py',
                'mimetype': 'text/x-python',
                'name': 'python',
                'nbconvert_exporter': 'python',
                'pygments_lexer': 'ipython3',
                'version': '3.8'
            }
        },
        'nbformat': 4,
        'nbformat_minor': 5
    }
    
    return notebook
