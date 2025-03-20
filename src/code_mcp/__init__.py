"""Code integration through the Model Context Protocol."""

__version__ = "0.1.0"

# Expose remote functionality
from code_mcp.remote import ssh_bridge_setup

"""
The remote module provides functionality to connect Claude Desktop
to a remote code-mcp instance running on another server via SSH.
"""
