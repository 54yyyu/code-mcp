#!/usr/bin/env python3
"""
Setup helper for Code-MCP

This script helps users set up Code-MCP with Claude Desktop by:
1. Finding the Claude Desktop config file
2. Adding the necessary configuration to the mcpServers section
3. Updating the configuration if it already exists
"""

import os
import json
import sys
import shutil
import subprocess
from pathlib import Path

def find_claude_config():
    """Find the Claude Desktop configuration file"""
    # Common locations for the Claude Desktop config file
    possible_locations = []
    
    # macOS
    if sys.platform == 'darwin':
        possible_locations.append(Path.home() / "Library/Application Support/Claude/config/claude_desktop_config.json")
    
    # Windows
    elif sys.platform == 'win32':
        app_data = os.environ.get('APPDATA', '')
        if app_data:
            possible_locations.append(Path(app_data) / "Claude/config/claude_desktop_config.json")
    
    # Linux
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
        possible_locations.append(Path(config_home) / "Claude/config/claude_desktop_config.json")
    
    # Check all possible locations
    for location in possible_locations:
        if location.exists():
            return location
    
    return None

def get_code_mcp_path():
    """Get the path to the code-mcp executable"""
    try:
        # Try to find the executable in the PATH
        code_mcp_path = shutil.which("code-mcp")
        if code_mcp_path:
            return code_mcp_path
    except Exception:
        pass
    
    # If not found, assume it's in the same package
    return "code-mcp"

def setup_claude_config(project_path=None):
    """Set up the Claude Desktop configuration for Code-MCP"""
    config_file = find_claude_config()
    
    if not config_file:
        print("Could not find Claude Desktop configuration file.")
        print("Please manually add the configuration to your Claude Desktop config.")
        print_manual_instructions(project_path)
        return False
    
    print(f"Found Claude Desktop configuration at: {config_file}")
    
    # Read the existing config
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If the file doesn't exist or is not valid JSON, start with an empty config
        config = {}
    
    # Ensure mcpServers section exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}
    
    # Get the project path if not provided
    if not project_path:
        print("\nEnter the path to your project directory:")
        project_path = input("> ").strip()
        
        # Expand the path in case it uses ~ or environment variables
        project_path = os.path.expanduser(project_path)
        project_path = os.path.expandvars(project_path)
        
        # Check if the path exists
        if not os.path.isdir(project_path):
            print(f"Error: Directory does not exist: {project_path}")
            return False
    
    # Get the code-mcp path
    code_mcp_path = get_code_mcp_path()
    
    # Create the configuration
    code_mcp_config = {
        "command": code_mcp_path,
        "args": [project_path]
    }
    
    # Add to the config
    config['mcpServers']['code'] = code_mcp_config
    
    # Write the updated config back to the file
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\nSuccessfully updated Claude Desktop configuration!")
        print("Please restart Claude Desktop for the changes to take effect.")
        return True
    except Exception as e:
        print(f"Error updating configuration file: {str(e)}")
        print_manual_instructions(project_path)
        return False

def print_manual_instructions(project_path=None):
    """Print instructions for manual configuration"""
    print("\nManual Configuration Instructions:")
    print("1. Open Claude Desktop")
    print("2. Go to Settings > Developer > Edit Config")
    print("3. Add the following to your claude_desktop_config.json:")
    
    path_placeholder = project_path or "/path/to/your/project"
    
    print("""
{
    "mcpServers": {
        "code": {
            "command": "code-mcp",
            "args": [
                "%s"
            ]
        }
    }
}
""" % path_placeholder)
    
    print("4. Save the file and restart Claude Desktop")

def main():
    """Main function"""
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Code-MCP Setup Helper: Configure Claude Desktop to use Code-MCP."
    )
    parser.add_argument("project_path", nargs="?", default=None,
                        help="Path to the project directory. If not provided, you will be prompted.")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle version flag
    if args.version:
        import code_mcp
        print(f"Code-MCP Setup Helper version {code_mcp.__version__}")
        return 0
    
    print("Code-MCP Setup Helper")
    print("=====================")
    print("This utility will help you configure Claude Desktop to use Code-MCP.")
    
    # Get project path from command line if provided
    project_path = args.project_path
    if project_path:
        # Expand the path
        project_path = os.path.expanduser(project_path)
        project_path = os.path.expandvars(project_path)
        
        # Check if the path exists
        if not os.path.isdir(project_path):
            print(f"Error: Directory does not exist: {project_path}")
            sys.exit(1)
    
    # Run the setup
    success = setup_claude_config(project_path)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
if __name__ == "__main__":
    main()