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
        possible_locations.append(Path.home() / "Library/Application Support/Claude/claude_desktop_config.json")
    
    # Windows
    elif sys.platform == 'win32':
        app_data = os.environ.get('APPDATA', '')
        if app_data:
            possible_locations.append(Path(app_data) / "Claude/claude_desktop_config.json")
    
    # Linux
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
        possible_locations.append(Path(config_home) / "Claude/claude_desktop_config.json")
    
    # Check all possible locations
    for location in possible_locations:
        if location.exists():
            return location
    
    return None

def get_code_mcp_path():
    """Get the path to the code-mcp executable"""
    # First, try to use just the command name (preferred)
    if shutil.which("code-mcp"):
        return "code-mcp"
    
    # If not found in PATH, try to find the absolute path
    script_path = None
    
    # Check common installation locations
    common_paths = [
        os.path.expanduser("~/.local/bin/code-mcp"),
        os.path.expanduser("~/mambaforge/bin/code-mcp"),
        os.path.expanduser("~/.uv/bin/code-mcp"),
        os.path.expanduser("~/.astral/uv/bin/code-mcp"),
        "/usr/local/bin/code-mcp",
        "/opt/homebrew/bin/code-mcp"
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            script_path = path
            break
    
    # If found, return the absolute path but warn the user
    if script_path:
        print(f"Warning: code-mcp not found in PATH, using absolute path: {script_path}")
        print("This may cause issues if you move or reinstall the package.")
        print("Consider adding the directory to your PATH.")
        return script_path
    
    # If still not found, use the basic command and hope for the best
    print("Warning: code-mcp not found in PATH. Using 'code-mcp' and hoping it works.")
    print("If this fails, you may need to specify the full path in the configuration.")
    return "code-mcp"

def fix_path_in_config(config):
    """Fix absolute paths in the config to use PATH-based commands"""
    updated = False
    
    if 'mcpServers' in config and 'code' in config['mcpServers']:
        code_server = config['mcpServers']['code']
        if 'command' in code_server:
            old_command = code_server['command']
            
            # If it's an absolute path to code-mcp, replace with just the command name
            if os.path.basename(old_command) == 'code-mcp':
                code_server['command'] = 'code-mcp'
                print(f"Updated command from '{old_command}' to 'code-mcp'")
                updated = True
                
                # Special case: if the command doesn't exist in PATH but we have a valid absolute path
                # Create a symlink to the actual command or provide instructions
                if not shutil.which('code-mcp') and os.path.isfile(old_command):
                    try:
                        # Try to create a symlink in ~/.local/bin
                        local_bin = os.path.expanduser('~/.local/bin')
                        if not os.path.exists(local_bin):
                            os.makedirs(local_bin, exist_ok=True)
                            
                        symlink_path = os.path.join(local_bin, 'code-mcp')
                        if os.path.exists(symlink_path):
                            os.remove(symlink_path)
                            
                        os.symlink(old_command, symlink_path)
                        print(f"Created a symlink from {old_command} to {symlink_path}")
                        print(f"Make sure {local_bin} is in your PATH")
                        
                        # Add to shell configs if missing
                        for rc_file in ['.bashrc', '.zshrc', '.bash_profile', '.profile']:
                            rc_path = os.path.expanduser(f'~/{rc_file}')
                            if os.path.isfile(rc_path):
                                with open(rc_path, 'r') as f:
                                    content = f.read()
                                    
                                if local_bin not in content:
                                    with open(rc_path, 'a') as f:
                                        f.write(f'\n# Added by code-mcp-setup\nexport PATH="{local_bin}:$PATH"\n')
                                    print(f"Added {local_bin} to PATH in {rc_file}")
                    except Exception as e:
                        print(f"Warning: Could not create symlink - {str(e)}")
                        print(f"You can continue to use the absolute path in your config:")
                        print(f"  '{old_command}'")
                        # Revert the change
                        code_server['command'] = old_command
                        updated = False
    
    return updated

def setup_claude_config(project_path=None, fix_path_only=False):
    """Set up the Claude Desktop configuration for Code-MCP"""
    config_file = find_claude_config()
    
    if not config_file:
        print("Could not find Claude Desktop configuration file.")
        if not fix_path_only:
            print("Please manually add the configuration to your Claude Desktop config.")
            print_manual_instructions(project_path)
        else:
            print("No configuration found to fix.")
        return False
    
    print(f"Found Claude Desktop configuration at: {config_file}")
    
    # Read the existing config
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If the file doesn't exist or is not valid JSON, start with an empty config
        if fix_path_only:
            print("Error reading configuration file.")
            return False
        config = {}
    
    # Always fix paths in the config, even in normal setup mode
    if 'mcpServers' in config and 'code' in config['mcpServers']:
        fixed = fix_path_in_config(config)
        if fixed and fix_path_only:
            try:
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                print("\nSuccessfully updated Claude Desktop configuration!")
                print("Please restart Claude Desktop for the changes to take effect.")
                return True
            except Exception as e:
                print(f"Error updating configuration file: {str(e)}")
                return False
        elif fix_path_only:
            print("No paths needed fixing in the configuration.")
            return True
    elif fix_path_only:
        print("No Code-MCP configuration found to fix.")
        return False
    
    # For normal setup, continue with configuration
    
    # Ensure mcpServers section exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}
    
    # Get the project path if not provided
    if not project_path:
        current_dir = os.getcwd()
        use_current = input(f"\nUse current directory as project path? ({current_dir}) [Y/n]: ").strip().lower()
        
        if not use_current or use_current in ('y', 'yes'):
            project_path = current_dir
            print(f"Using current directory: {project_path}")
        else:
            print("\nEnter the path to your project directory:")
            project_path = input("> ").strip()
            
            # Expand the path in case it uses ~ or environment variables
            project_path = os.path.expanduser(project_path)
            project_path = os.path.expandvars(project_path)
    
    # Check if the path exists
    if not os.path.isdir(project_path):
        print(f"Error: Directory does not exist: {project_path}")
        return False
    
    # Get the code-mcp path (always use the simple command name to use PATH)
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
    parser.add_argument("--fix-path", action="store_true", 
                        help="Only fix path issues in existing configuration")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle version flag
    if args.version:
        import code_mcp
        print(f"Code-MCP Setup Helper version {code_mcp.__version__}")
        return 0
    
    # Handle fix-path mode
    if args.fix_path:
        print("Code-MCP Path Fix Helper")
        print("=======================")
        print("This utility will update your Claude Desktop configuration to use code-mcp from your PATH.")
        
        # Run the fix
        success = setup_claude_config(fix_path_only=True)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
    
    # Regular setup mode
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