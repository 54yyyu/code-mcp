"""
Jupyter notebook utilities for the Code-MCP package.

This module provides functions for working with and manipulating Jupyter notebooks (.ipynb files),
with a focus on notebook structure manipulation rather than execution.
"""

import json
import logging
import base64
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

def extract_cell_outputs(cell: Dict) -> List[Dict]:
    """
    Extract outputs from a cell including rich content like images.
    
    Args:
        cell: Cell dictionary
        
    Returns:
        List of output dictionaries with processed content
    """
    if cell.get('cell_type') != 'code' or 'outputs' not in cell:
        return []
    
    processed_outputs = []
    
    for output in cell.get('outputs', []):
        output_type = output.get('output_type')
        
        if output_type == 'stream':
            # Text output (stdout/stderr)
            processed_outputs.append({
                'type': 'text',
                'name': output.get('name', 'stdout'),
                'content': "".join(output.get('text', [])) if isinstance(output.get('text'), list) else output.get('text', '')
            })
        
        elif output_type == 'execute_result' or output_type == 'display_data':
            # Handle different data formats
            if 'data' in output:
                data = output['data']
                
                # Text output
                if 'text/plain' in data:
                    text = data['text/plain']
                    text_content = "".join(text) if isinstance(text, list) else text
                    processed_outputs.append({
                        'type': 'text',
                        'name': 'result',
                        'content': text_content
                    })
                
                # HTML output
                if 'text/html' in data:
                    html = data['text/html']
                    html_content = "".join(html) if isinstance(html, list) else html
                    processed_outputs.append({
                        'type': 'html',
                        'content': html_content
                    })
                
                # Image output
                for mime_type in ['image/png', 'image/jpeg', 'image/svg+xml']:
                    if mime_type in data:
                        # For PNG/JPEG, data is base64-encoded
                        if mime_type in ['image/png', 'image/jpeg']:
                            image_data = data[mime_type]
                            processed_outputs.append({
                                'type': 'image',
                                'mime_type': mime_type,
                                'data': image_data if isinstance(image_data, str) else "".join(image_data)
                            })
                        # For SVG, data is XML
                        elif mime_type == 'image/svg+xml':
                            svg_data = data[mime_type]
                            processed_outputs.append({
                                'type': 'svg',
                                'content': svg_data if isinstance(svg_data, str) else "".join(svg_data)
                            })
        
        elif output_type == 'error':
            # Error output
            error_name = output.get('ename', 'Error')
            error_value = output.get('evalue', '')
            error_traceback = output.get('traceback', [])
            
            if isinstance(error_traceback, list):
                error_traceback = "\n".join(error_traceback)
            
            processed_outputs.append({
                'type': 'error',
                'name': error_name,
                'value': error_value,
                'traceback': error_traceback
            })
    
    return processed_outputs

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

def convert_notebook_to_python(notebook: Dict) -> str:
    """
    Convert a notebook to Python code.
    
    Args:
        notebook: Notebook dictionary
        
    Returns:
        String containing Python code
    """
    cells = get_notebook_cells(notebook)
    python_code = []
    
    for i, cell in enumerate(cells):
        cell_type = get_cell_type(cell)
        content = extract_cell_content(cell)
        
        if cell_type == 'code':
            # Add code cells directly
            python_code.append(content)
        elif cell_type == 'markdown':
            # Convert markdown to Python comments
            comment_lines = []
            for line in content.splitlines():
                comment_lines.append(f"# {line}")
            python_code.append("\n".join(comment_lines))
        # Ignore raw cells
    
    return "\n\n".join(python_code)
