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
    
    return resultcomment_lines))
        # Ignore raw cells
    
    return "\n\n".join(python_code)
