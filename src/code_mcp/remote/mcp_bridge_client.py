#!/usr/bin/env python3
"""
MCP Bridge Client

A script that forwards stdio communication from Claude Desktop to
an HTTP bridge server and returns responses.
"""

import argparse
import asyncio
import json
import logging
import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Third-party imports
import httpx

# Configure logging to a writable location
log_dir = os.path.join(os.path.expanduser("~"), ".mcp_logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "mcp_bridge_client.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger("mcp_bridge_client")

class MCPBridgeClient:
    """Client that connects Claude Desktop to a remote code-mcp instance through an HTTP bridge"""
    
    def __init__(self, bridge_url: str, server_path: str, project_path: str, 
                 timeout: int = 120, heartbeat_interval: int = 30, 
                 auth_token: Optional[str] = None):
        """Initialize the bridge client"""
        self.bridge_url = bridge_url
        self.server_path = server_path
        self.project_path = project_path
        self.timeout = timeout
        self.heartbeat_interval = heartbeat_interval
        self.auth_token = auth_token
        self.last_activity = time.time()
        self.running = True
        self.request_history = []
        self.session_id = f"client_{int(time.time())}"
        
        logger.info(f"Initialized with bridge_url={bridge_url}, server_path={server_path}, "
                    f"project_path={project_path}, timeout={timeout}s, "
                    f"heartbeat_interval={heartbeat_interval}s")
    
    async def send_heartbeat(self):
        """Send periodic heartbeats to keep the connection alive"""
        while self.running:
            try:
                # Only send heartbeat if we've been inactive for a while
                time_since_activity = time.time() - self.last_activity
                if time_since_activity > self.heartbeat_interval / 2:
                    logger.info(f"Sending heartbeat (inactive for {time_since_activity:.1f}s)")
                    
                    # Use a simple no-op request as heartbeat (list_tools)
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        headers = self._get_headers()
                        
                        bridge_request = {
                            "method": "tools/list",
                            "serverPath": self.server_path,
                            "args": [self.project_path],
                            "params": {}
                        }
                        
                        response = await client.post(
                            self.bridge_url,
                            json=bridge_request,
                            headers=headers,
                            timeout=self.timeout
                        )
                        
                        # Check for HTTP errors
                        response.raise_for_status()
                        
                        # Update last activity
                        self.last_activity = time.time()
                    
            except Exception as e:
                logger.error(f"Error sending heartbeat: {str(e)}")
            
            # Wait for the next heartbeat interval
            await asyncio.sleep(self.heartbeat_interval)
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single JSON-RPC request"""
        try:
            # Ensure id is not None or undefined
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            logger.info(f"Processing request: id={request_id}, method={method}")
            
            # Ensure request_id is always a valid type (string or number)
            if request_id is None:
                # Generate a default ID if not provided
                request_id = str(int(time.time() * 1000))
            
            # Validate method is a non-empty string
            if not method or not isinstance(method, str):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: method must be a non-empty string"
                    }
                }
            
            # Keep track of important requests in history
            if method in ["initialize", "tools/list", "resources/list"]:
                self.request_history.append({
                    "id": request_id,
                    "method": method,
                    "time": time.time()
                })
            
            # Update last activity time
            self.last_activity = time.time()
            
            # Special handling for notification
            is_notification = method.startswith("notifications/") if method else False
            
            # Forward the request to the bridge server
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = self._get_headers()
                
                bridge_request = {
                    "method": method,
                    "serverPath": self.server_path,
                    "args": [self.project_path],
                    "params": params,
                    "env": {}
                }
                
                logger.debug(f"Sending to bridge: {json.dumps(bridge_request)}")
                
                response = await client.post(
                    self.bridge_url,
                    json=bridge_request,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Get the response from the bridge server
                bridge_response = response.json()
                
                # For notifications, return an empty successful response
                if is_notification:
                    return {
                        "jsonrpc": "2.0", 
                        "id": request_id, 
                        "result": {}
                    }
                
                # Handle error responses
                if "error" in bridge_response:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": bridge_response["error"] if isinstance(bridge_response["error"], dict) else {
                            "code": -32000,
                            "message": f"Remote MCP error: {bridge_response['error']}"
                        }
                    }
                
                # For tools/list method, modify the result to add "remote-" prefix to each tool
                if method == "tools/list" and "result" in bridge_response:
                    result = bridge_response["result"]
                    if isinstance(result, list):
                        for tool in result:
                            if isinstance(tool, dict) and "name" in tool:
                                tool["name"] = f"remote-{tool['name']}"
                
                # Normalize the response to strict JSON-RPC 2.0 format
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": bridge_response.get("result", bridge_response)
                }
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"HTTP error: {e.response.status_code}"
                }
            }
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"Network error: {str(e)}"
                }
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"Bridge client error: {str(e)}"
                }
            }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests to the bridge server"""
        headers = {
            "Content-Type": "application/json",
            "X-MCP-Client-ID": self.session_id
        }
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        return headers
    
    async def start(self):
        """Run the bridge client"""
        logger.info(f"Starting MCP Bridge Client for remote code-mcp")
        logger.info(f"Connected to bridge at {self.bridge_url}")
        logger.info(f"Remote server path: {self.server_path}")
        logger.info(f"Remote project path: {self.project_path}")
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self.send_heartbeat())
        
        try:
            # Read from stdin and write to stdout
            stdin_reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(stdin_reader)
            await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
            
            # Process incoming requests
            while True:
                # Read a line from stdin
                line = await stdin_reader.readline()
                if not line:
                    logger.info("End of input, exiting")
                    break
                
                logger.debug(f"Received input: {line.strip()}")
                
                try:
                    # Parse the JSON-RPC request
                    request = json.loads(line)
                    
                    # Process the request
                    response = await self.process_request(request)
                    
                    # Write the response to stdout
                    response_str = json.dumps(response) + "\n"
                    sys.stdout.write(response_str)
                    sys.stdout.flush()
                    logger.debug(f"Sent response: {response_str.strip()}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    # Skip invalid input
                    continue
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    # Try to send an error response if possible
                    try:
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32000,
                                "message": f"Unexpected error: {str(e)}"
                            }
                        }
                        sys.stdout.write(json.dumps(error_response) + "\n")
                        sys.stdout.flush()
                    except:
                        # If we can't send an error response, just continue
                        pass
        
        except Exception as e:
            logger.error(f"Fatal error in start(): {e}", exc_info=True)
        finally:
            # Stop the heartbeat
            self.running = False
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
            logger.info("MCP Bridge Client stopped")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Bridge Client for Remote Code-MCP")
    parser.add_argument("--bridge-url", default="http://localhost:3000/bridge",
                        help="URL of the bridge server (default: http://localhost:3000/bridge)")
    parser.add_argument("--server-path", default="code-mcp",
                        help="Path to the MCP server executable on the remote host (default: code-mcp)")
    parser.add_argument("--project-path", default=os.path.expanduser("~/project"),
                        help="Path to the project directory on the remote host (default: ~/project)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Request timeout in seconds (default: 120)")
    parser.add_argument("--heartbeat-interval", type=int, default=30,
                        help="Interval between heartbeats in seconds (default: 30)")
    parser.add_argument("--auth-token", default=os.environ.get("MCP_BRIDGE_AUTH_TOKEN"),
                        help="Auth token for the bridge server (can also be set via MCP_BRIDGE_AUTH_TOKEN env var)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create and run the bridge client
    client = MCPBridgeClient(
        args.bridge_url, 
        args.server_path, 
        args.project_path, 
        args.timeout,
        args.heartbeat_interval,
        args.auth_token
    )
    await client.start()


if __name__ == "__main__":
    asyncio.run(main())