#!/usr/bin/env python3
"""
Remote Code-MCP Bridge - Connect Claude Desktop to remote code-mcp instances

This bridge runs on the remote server and manages stdio communication with code-mcp,
exposing an HTTP interface for the local bridge client.
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import queue
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RemoteCodeMCPBridge")

# Global variables
request_queue = queue.Queue()
response_map = {}
response_lock = threading.Lock()

class CodeMCPProcess:
    """Manages a code-mcp subprocess with stdio communication"""
    
    def __init__(self, code_mcp_path: str, project_path: str):
        """Initialize with paths to code-mcp and the project directory"""
        self.code_mcp_path = code_mcp_path
        self.project_path = project_path
        self.process = None
        self.running = False
        self.next_id = 1
        self.id_lock = threading.Lock()
        
        logger.info(f"Initializing code-mcp process handler: {code_mcp_path} {project_path}")
    
    def start(self):
        """Start the code-mcp process"""
        if self.process is not None and self.process.poll() is None:
            logger.warning("Attempting to start code-mcp process that's already running")
            return True
        
        logger.info(f"Starting code-mcp: {self.code_mcp_path} {self.project_path}")
        
        try:
            # Start the code-mcp process
            self.process = subprocess.Popen(
                [self.code_mcp_path, self.project_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )
            
            # Start workers to handle stdin and stdout
            self.running = True
            
            # Start stdout reader thread
            stdout_thread = threading.Thread(target=self._stdout_worker)
            stdout_thread.daemon = True
            stdout_thread.start()
            
            # Start stderr reader thread
            stderr_thread = threading.Thread(target=self._stderr_worker)
            stderr_thread.daemon = True
            stderr_thread.start()
            
            # Start stdin writer thread
            stdin_thread = threading.Thread(target=self._stdin_worker)
            stdin_thread.daemon = True
            stdin_thread.start()
            
            logger.info("code-mcp process started")
            
            # Wait a moment for the process to initialize
            time.sleep(1)
            
            # Check if process is still alive
            if self.process.poll() is not None:
                logger.error(f"code-mcp process exited with code {self.process.poll()}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error starting code-mcp: {e}")
            return False
    
    def _stdin_worker(self):
        """Worker to send requests to code-mcp's stdin"""
        try:
            while self.running and self.process and self.process.poll() is None:
                try:
                    # Get the next request from the queue with a timeout
                    request = request_queue.get(timeout=0.5)
                    
                    # Log the request (excluding initialize parameters for brevity)
                    if '"method":"initialize"' in request:
                        logger.debug("Sending initialize request to code-mcp")
                    else:
                        logger.debug(f"Sending to code-mcp: {request}")
                    
                    # Encode and send to stdin
                    self.process.stdin.write(request + "\n")
                    self.process.stdin.flush()
                    
                    request_queue.task_done()
                except queue.Empty:
                    # No requests in the queue, continue
                    continue
                except Exception as e:
                    logger.error(f"Error in stdin worker: {e}")
                    if self.process and self.process.poll() is not None:
                        # Process has exited
                        logger.error(f"code-mcp process exited with code {self.process.poll()}")
                        self.running = False
                        break
        except Exception as e:
            logger.error(f"Fatal error in stdin worker: {e}")
            self.running = False
    
    def _stdout_worker(self):
        """Worker to read responses from code-mcp's stdout"""
        try:
            while self.running and self.process and self.process.poll() is None:
                # Read a line from stdout
                line = self.process.stdout.readline()
                if not line:
                    # End of file reached, process has closed stdout
                    logger.warning("code-mcp stdout closed")
                    self.running = False
                    break
                
                try:
                    # Check if the line is a valid JSON response
                    if line.strip().startswith('{') and line.strip().endswith('}'):
                        # Parse the JSON response
                        response = json.loads(line)
                        
                        # Extract the request ID
                        response_id = response.get('id')
                        if response_id is not None:
                            # Store the response
                            with response_lock:
                                response_map[response_id] = response
                        else:
                            # Handle notifications (no ID)
                            logger.info(f"Received notification from code-mcp: {response}")
                    else:
                        # Non-JSON output
                        logger.info(f"Non-JSON output from code-mcp: {line.strip()}")
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in stdout: {e}, data: {line}")
                except Exception as e:
                    logger.error(f"Error processing stdout: {e}")
        
        except Exception as e:
            logger.error(f"Error in stdout worker: {e}")
            self.running = False
    
    def _stderr_worker(self):
        """Worker to log stderr output from code-mcp"""
        try:
            while self.running and self.process and self.process.poll() is None:
                # Read a line from stderr
                line = self.process.stderr.readline()
                if not line:
                    # End of file reached, process has closed stderr
                    break
                
                # Log stderr output
                stderr_line = line.strip()
                if stderr_line:
                    logger.info(f"code-mcp stderr: {stderr_line}")
        except Exception as e:
            logger.error(f"Error in stderr worker: {e}")
    
    def send_request(self, method, params=None, is_notification=False):
        """Send a request to code-mcp and wait for a response"""
        if not self.running or not self.process or self.process.poll() is not None:
            if not self.start():
                return {"error": "Failed to start code-mcp process"}
        
        # Create request
        with self.id_lock:
            request_id = None if is_notification else self.next_id
            self.next_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if params is not None:
            request["params"] = params
        
        if not is_notification:
            request["id"] = request_id
        
        # Convert to JSON and add to queue
        request_json = json.dumps(request)
        request_queue.put(request_json)
        
        # If it's a notification, return immediately
        if is_notification:
            return {}
        
        # Wait for the response with timeout
        timeout = 30  # 30 seconds timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if the process is still running
            if self.process.poll() is not None:
                return {"error": f"code-mcp process exited with code {self.process.poll()}"}
                
            with response_lock:
                if request_id in response_map:
                    response = response_map[request_id]
                    del response_map[request_id]
                    
                    # Return the complete response, don't modify it
                    return response
            
            # Sleep briefly before checking again
            time.sleep(0.1)
        
        # Timeout occurred
        return {"error": "Request timed out"}
    
    def stop(self):
        """Stop the code-mcp process"""
        logger.info("Stopping code-mcp process")
        self.running = False
        
        if self.process:
            # Try to terminate gracefully
            try:
                self.process.terminate()
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                logger.warning("code-mcp didn't terminate gracefully, killing")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping code-mcp: {e}")
            
            self.process = None
        
        logger.info("code-mcp process stopped")


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that forwards requests to code-mcp"""
    
    def __init__(self, *args, code_mcp_manager=None, **kwargs):
        self.code_mcp_manager = code_mcp_manager
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests to forward to code-mcp"""
        # Get content length
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # Check path
        if self.path != '/bridge':
            self.send_response(404)
            self.end_headers()
            return
        
        # Parse the request
        try:
            bridge_request = json.loads(post_data.decode('utf-8'))
            method = bridge_request.get("method")
            params = bridge_request.get("params", {})
            
            logger.info(f"Received bridge request: {method}")
            
            if method == "tools/call" and isinstance(params, dict) and "name" in params:
                if params["name"].startswith("remote_"):
                    params["name"] = params["name"].replace("remote_", "", 1)
            
            # Check if this is a notification (no response expected)
            is_notification = method.startswith("notifications/") if method else False
            
            # Process the request
            result = self.code_mcp_manager.send_request(method, params, is_notification)
            
            # Add "remote_" prefix to tool names in tools/list response
            if method == "tools/list" and isinstance(result, dict) and "result" in result:
                result_object = result.get("result")
                if isinstance(result_object, dict) and "tools" in result_object:
                    tools_list = result_object.get("tools")
                    if isinstance(tools_list, list):
                        for tool in tools_list:
                            if isinstance(tool, dict) and "name" in tool:
                                tool["name"] = f"remote_{tool['name']}"
            
            # Send the response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Failed to process request: {str(e)}"
            }).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests (health check)"""
        if self.path == '/health':
            # Check if code-mcp is running
            is_running = (self.code_mcp_manager.process is not None and 
                         self.code_mcp_manager.process.poll() is None)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok" if is_running else "error",
                "code_mcp_running": is_running
            }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(format % args)


class RemoteCodeMCPBridge:
    """Bridge running on the remote server to connect code-mcp to HTTP clients"""
    
    def __init__(self, code_mcp_path: str, project_path: str, http_port: int, auth_token: Optional[str] = None):
        """Initialize the bridge"""
        self.code_mcp_path = code_mcp_path
        self.project_path = project_path
        self.http_port = http_port
        self.auth_token = auth_token
        self.http_server = None
        self.running = False
        
        # Create code-mcp process manager
        self.code_mcp_manager = CodeMCPProcess(code_mcp_path, project_path)
    
    def start(self):
        """Start the bridge"""
        logger.info("Starting Remote Code-MCP Bridge")
        
        # Start the HTTP server
        if not self._start_http_server():
            logger.error("Failed to start HTTP server, exiting")
            return False
        
        # Print connection info
        self._print_connection_info()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Mark as running
        self.running = True
        
        return True
    
    def _start_http_server(self):
        """Start the HTTP server to handle requests from clients"""
        
        # Create a custom handler factory that has access to our code-mcp manager
        def handler_factory(*args, **kwargs):
            return MCPRequestHandler(*args, code_mcp_manager=self.code_mcp_manager, **kwargs)
        
        try:
            # Start the server in a separate thread
            self.http_server = HTTPServer(('0.0.0.0', self.http_port), handler_factory)
            server_thread = threading.Thread(target=self.http_server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            logger.info(f"HTTP server started on port {self.http_port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            return False
    
    def _print_connection_info(self):
        """Print information about the bridge"""
        
        print("\n=================================================")
        print("Remote Code-MCP Bridge is running!")
        print("=================================================")
        print(f"\nHTTP server running on port {self.http_port}")
        print(f"code-mcp path: {self.code_mcp_path}")
        print(f"Project path: {self.project_path}")
        print("\nUse the local bridge client to connect to this bridge.")
        print("\nPress Ctrl+C to stop the bridge.")
        print("=================================================\n")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: self.stop())
    
    def stop(self):
        """Stop the bridge"""
        logger.info("Stopping Remote Code-MCP Bridge")
        
        # Stop the HTTP server
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        
        # Stop code-mcp
        if self.code_mcp_manager:
            self.code_mcp_manager.stop()
        
        # Mark as not running
        self.running = False
        
        logger.info("Remote Code-MCP Bridge stopped")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Remote Code-MCP Bridge - Connect Claude Desktop to code-mcp on a remote server"
    )
    
    # Arguments
    parser.add_argument("--code-mcp-path", default="code-mcp",
                       help="Path to the code-mcp executable (default: code-mcp in PATH)")
    parser.add_argument("--project-path", default=os.path.expanduser("~/project"),
                       help="Path to the project directory (default: ~/project)")
    parser.add_argument("--port", type=int, default=5000,
                       help="Port for the HTTP server (default: 5000)")
    parser.add_argument("--auth-token",
                       help="Authentication token for HTTP requests")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Start the bridge
    bridge = RemoteCodeMCPBridge(
        code_mcp_path=args.code_mcp_path,
        project_path=args.project_path,
        http_port=args.port,
        auth_token=args.auth_token
    )
    
    try:
        if bridge.start():
            # Keep the main thread alive
            while bridge.running:
                time.sleep(1)
            return 0
        else:
            return 1
    except Exception as e:
        logger.error(f"Failed to start bridge: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        bridge.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
