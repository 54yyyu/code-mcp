"""
Remote MCP Bridge - Connect Claude Desktop to remote code-mcp instances.

This package provides functionality to connect Claude Desktop
to a remote code-mcp instance running on another server via SSH.
"""

from code_mcp.remote.ssh_bridge_setup import main as setup_main
from code_mcp.remote.mcp_bridge_client import MCPBridgeClient
from code_mcp.remote.remote_bridge_server import RemoteCodeMCPBridge

__all__ = [
    'MCPBridgeClient',
    'RemoteCodeMCPBridge',
    'setup_main',
]
