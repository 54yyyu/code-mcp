"""
Remote Tools Integration

This module provides helper functions to integrate remote tools
into the local code-mcp server.
"""

import logging
import json
from typing import Dict, Any, List, Callable, Optional, Tuple

logger = logging.getLogger("remote_tools")

class RemoteToolsRegistry:
    """Registry for remote tools that are proxied through the local server"""
    
    def __init__(self):
        """Initialize the registry"""
        self.remote_tool_handlers = {}
        self.tool_metadata = {}
    
    def register_remote_tool(self, tool_name: str, handler: Callable, metadata: Dict[str, Any]):
        """Register a remote tool handler"""
        self.remote_tool_handlers[tool_name] = handler
        self.tool_metadata[tool_name] = metadata
        logger.info(f"Registered remote tool: {tool_name}")
    
    def is_remote_tool(self, tool_name: str) -> bool:
        """Check if a tool is a remote tool"""
        return tool_name.startswith("remote-") or tool_name.startswith("remote_")
    
    def get_remote_tools(self) -> List[Dict[str, Any]]:
        """Get a list of all remote tools"""
        return list(self.tool_metadata.values())
    
    def get_remote_tool_handler(self, tool_name: str) -> Optional[Callable]:
        """Get the handler for a remote tool"""
        # Remove the "remote-" or "remote_" prefix if present
        local_name = tool_name
        if tool_name.startswith("remote-"):
            local_name = tool_name[len("remote-"):]
        elif tool_name.startswith("remote_"):
            local_name = tool_name[len("remote_"):]
        
        return self.remote_tool_handlers.get(local_name)
    
    def handle_remote_tool_call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a call to a remote tool"""
        handler = self.get_remote_tool_handler(tool_name)
        
        if not handler:
            return {
                "error": f"Remote tool not found: {tool_name}"
            }
        
        try:
            return handler(params)
        except Exception as e:
            logger.error(f"Error calling remote tool {tool_name}: {e}")
            return {
                "error": f"Error calling remote tool: {str(e)}"
            }

# Singleton instance
remote_tools = RemoteToolsRegistry()

def parse_remote_tool_name(tool_name: str) -> Tuple[str, str]:
    """Parse a remote tool name into remote name and tool name"""
    
    # Default format is "remote-[tool_name]"
    if tool_name.startswith("remote-"):
        return "remote", tool_name[len("remote-"):]
    
    # Alternative format "remote_[tool_name]"
    if tool_name.startswith("remote_"):
        return "remote", tool_name[len("remote_"):]
    
    # Not a remote tool
    return "", tool_name
