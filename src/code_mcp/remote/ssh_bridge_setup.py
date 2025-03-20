#!/usr/bin/env python3
"""
Remote MCP Bridge Setup

This script automates the setup of a remote MCP bridge connection:
1. Uploads the bridge server script to the remote server
2. Starts the bridge server on the remote machine
3. Sets up an SSH tunnel locally
4. Configures the Claude Desktop config file
"""

import os
import sys
import json
import argparse
import subprocess
import time
import signal
import atexit
import platform
import tempfile
import psutil  # New dependency for better process management

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Set up a remote MCP bridge connection")
    
    parser.add_argument("--remote-host", required=True, 
                        help="Remote host to connect to (e.g., user@hostname)")
    
    parser.add_argument("--remote-project-path", default="~/project",
                        help="Path to the project directory on the remote host (default: ~/project)")
    
    parser.add_argument("--local-port", type=int, default=3000,
                        help="Local port for the SSH tunnel (default: 3000)")
    
    parser.add_argument("--remote-port", type=int, default=5000,
                        help="Remote port for the bridge server (default: 5000)")
    
    parser.add_argument("--code-mcp-path", default="code-mcp",
                        help="Path to the code-mcp executable on the remote host (default: code-mcp)")
    
    parser.add_argument("--auth-token", default=None,
                        help="Authentication token for the bridge server")
    
    parser.add_argument("--ssh-key", default=None,
                        help="Path to SSH private key file")
    
    return parser.parse_args()

def get_claude_config_path():
    """Get the path to the Claude Desktop config file based on the OS"""
    if platform.system() == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    elif platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
    else:
        print("Warning: Unsupported OS. Using default config path.")
        return os.path.expanduser("~/.config/claude/claude_desktop_config.json")

def read_claude_config():
    """Read the Claude Desktop config file, creating it if it doesn't exist"""
    config_path = get_claude_config_path()
    config_dir = os.path.dirname(config_path)
    
    # Create config directory if it doesn't exist
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # Create or read config file
    if not os.path.exists(config_path):
        return {"mcpServers": {}}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Malformed config file at {config_path}. Creating new config.")
        return {"mcpServers": {}}

def write_claude_config(config):
    """Write the Claude Desktop config file"""
    config_path = get_claude_config_path()
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Updated Claude Desktop config at {config_path}")
    print("Claude Desktop config updated with remote-code-mcp server")
    print("Please restart Claude Desktop to apply the changes")

def create_ssh_controlmaster(remote_host, ssh_key=None):
    """Create SSH ControlMaster for persistent connection"""
    print(f"Setting up persistent SSH connection to {remote_host}...")
    
    # Create temporary directory for socket
    temp_dir = tempfile.mkdtemp(prefix="ssh-cm-")
    socket_path = os.path.join(temp_dir, "ssh_socket")
    
    # Build SSH command
    ssh_args = ["ssh"]
    
    if ssh_key:
        ssh_args.extend(["-i", ssh_key])
    
    ssh_args.extend([
        "-o", f"ControlPath={socket_path}",
        "-o", "ControlMaster=yes",
        "-o", "ControlPersist=yes",
        "-o", "ConnectTimeout=20",  # Add connection timeout
        "-o", "ServerAliveInterval=10",  # Keep connection alive
        remote_host,
        "echo 'Control master connection established'"
    ])
    
    # Start the control master
    print("Please enter your password when prompted (you'll only need to do this once)")
    try:
        process = subprocess.run(ssh_args, check=False, timeout=30)  # Add timeout
        
        if process.returncode != 0:
            print("Failed to establish SSH connection")
            return None
        
        print("SSH connection established successfully")
        return socket_path
    except subprocess.TimeoutExpired:
        print("Timeout while establishing SSH connection")
        # Clean up the temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

def run_ssh_command(remote_host, command, control_path=None, ssh_key=None, timeout=60):
    """Run a command over SSH using control socket if available"""
    ssh_args = ["ssh"]
    
    if ssh_key:
        ssh_args.extend(["-i", ssh_key])
    
    if control_path:
        ssh_args.extend(["-o", f"ControlPath={control_path}"])
    
    ssh_args.append(remote_host)
    ssh_args.append(command)
    
    try:
        process = subprocess.run(
            ssh_args,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout  # Add timeout parameter
        )
        return process.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"SSH command timed out after {timeout} seconds: {' '.join(ssh_args)}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"SSH command failed: {e.stderr}")
        return None

def run_scp_command(remote_host, local_path, remote_path, control_path=None, ssh_key=None):
    """Copy a file to the remote host using control socket if available"""
    scp_args = ["scp"]
    
    if ssh_key:
        scp_args.extend(["-i", ssh_key])
    
    if control_path:
        scp_args.extend(["-o", f"ControlPath={control_path}"])
    
    scp_args.extend([local_path, f"{remote_host}:{remote_path}"])
    
    try:
        subprocess.run(scp_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"SCP command failed: {e.stderr}")
        return False

def create_ssh_tunnel(remote_host, local_port, remote_port, control_path=None, ssh_key=None):
    """Create an SSH tunnel to the remote host using control socket if available"""
    print(f"Creating SSH tunnel from localhost:{local_port} to {remote_host}:{remote_port}...")
    
    ssh_args = ["ssh", "-N", "-L", f"{local_port}:localhost:{remote_port}"]
    
    if ssh_key:
        ssh_args.extend(["-i", ssh_key])
    
    if control_path:
        ssh_args.extend(["-o", f"ControlPath={control_path}"])
    
    ssh_args.append(remote_host)
    
    tunnel_process = subprocess.Popen(
        ssh_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a moment for the tunnel to establish
    time.sleep(2)
    
    # Check if the tunnel process is still running
    if tunnel_process.poll() is not None:
        stderr = tunnel_process.stderr.read().decode('utf-8')
        print(f"Failed to establish SSH tunnel: {stderr}")
        return None
    
    print("SSH tunnel established successfully")
    return tunnel_process

def kill_ssh_tunnel(tunnel_process, timeout=5):
    """Properly terminate an SSH tunnel process with fallback methods"""
    if tunnel_process is None or tunnel_process.poll() is not None:
        return  # Process is already terminated
    
    print("Terminating SSH tunnel...")
    
    try:
        # First try to terminate gracefully
        tunnel_process.terminate()
        
        # Wait for the process to terminate with timeout
        for _ in range(timeout):
            if tunnel_process.poll() is not None:
                print("SSH tunnel terminated gracefully")
                return
            time.sleep(1)
            
        # If termination didn't work, use SIGKILL
        print("Forcefully killing SSH tunnel...")
        tunnel_process.kill()
        tunnel_process.wait(timeout=2)
        
    except Exception as e:
        print(f"Error while terminating SSH tunnel: {e}")
        
        # As a last resort, use psutil to kill the process and its children
        try:
            process = psutil.Process(tunnel_process.pid)
            children = process.children(recursive=True)
            
            for child in children:
                try:
                    child.kill()
                except:
                    pass
                
            if process.is_running():
                process.kill()
                
            print("SSH tunnel forcefully killed")
        except:
            print("Warning: Could not kill SSH tunnel process. You may need to kill it manually.")

def update_claude_config(local_port, remote_project_path, code_mcp_path, client_script_path, auth_token=None):
    """Update the Claude Desktop config file"""
    # Read the current config
    config = read_claude_config()
    
    # Add the new server configuration
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Get Python executable path
    python_path = sys.executable
    
    # Build the server configuration
    server_config = {
        "command": python_path,
        "args": [
            client_script_path,
            "--bridge-url", f"http://localhost:{local_port}/bridge",
            "--server-path", code_mcp_path,
            "--project-path", remote_project_path
        ]
    }
    
    # Add authentication token if provided
    if auth_token:
        server_config["env"] = {
            "MCP_BRIDGE_AUTH_TOKEN": auth_token
        }
    
    # Add the server to the config
    config["mcpServers"]["remote-code-mcp"] = server_config
    
    # Write the config
    write_claude_config(config)

def check_and_install_code_mcp(remote_host, code_mcp_path, control_path=None, ssh_key=None):
    """Check if code-mcp is installed on the remote host and install it if needed"""
    print("Checking if code-mcp is installed on the remote server...")
    
    # Check if code-mcp exists and is executable
    check_cmd = f"which {code_mcp_path} || command -v {code_mcp_path} || echo 'NOT_FOUND'"
    check_result = run_ssh_command(
        remote_host,
        check_cmd,
        control_path,
        ssh_key,
        timeout=10
    )
    
    if check_result and "NOT_FOUND" not in check_result:
        print(f"Found code-mcp on remote server at: {check_result}")
        return True
    
    print("code-mcp not found on remote server. Attempting to install...")
    
    # Try to install code-mcp using pip or uv
    try:
        # First try to use uv if available (faster)
        install_cmd_uv = "command -v uv >/dev/null && uv pip install git+https://github.com/54yyyu/code-mcp.git || echo 'UV_NOT_FOUND'"
        uv_result = run_ssh_command(
            remote_host,
            install_cmd_uv,
            control_path,
            ssh_key,
            timeout=120  # Installation might take a while
        )
        
        if uv_result and "UV_NOT_FOUND" not in uv_result:
            print("Successfully installed code-mcp using uv")
            return True
        
        # Fall back to pip
        print("UV not found or installation failed. Trying with pip...")
        install_cmd_pip = "pip3 install --user git+https://github.com/54yyyu/code-mcp.git"
        pip_result = run_ssh_command(
            remote_host,
            install_cmd_pip,
            control_path,
            ssh_key,
            timeout=120
        )
        
        # Verify installation
        verify_cmd = "command -v code-mcp || echo 'NOT_FOUND'"
        verify_result = run_ssh_command(
            remote_host,
            verify_cmd,
            control_path,
            ssh_key,
            timeout=10
        )
        
        if verify_result and "NOT_FOUND" not in verify_result:
            print(f"Successfully installed code-mcp on remote server at: {verify_result}")
            return True
        else:
            print(f"Installation verification failed. Please install code-mcp manually on {remote_host}")
            return False
            
    except Exception as e:
        print(f"Error installing code-mcp: {e}")
        print(f"Please install code-mcp manually on {remote_host}")
        return False

def kill_remote_processes(remote_host, server_pid, remote_port, control_path=None, ssh_key=None):
    """Kill the remote server process and any related processes"""
    print(f"Terminating remote server process (PID: {server_pid}) and all its children...")
    
    # First try to find any processes using the port
    port_check_cmd = f"lsof -i :{remote_port} | grep LISTEN | awk '{{print $2}}' || echo ''"
    port_pids = run_ssh_command(
        remote_host,
        port_check_cmd,
        control_path,
        ssh_key,
        timeout=5
    )
    
    # Kill processes by port first (most reliable)
    if port_pids and port_pids.strip():
        for pid in port_pids.strip().split('\n'):
            if pid:
                run_ssh_command(
                    remote_host,
                    f"kill -9 {pid.strip()}",
                    control_path,
                    ssh_key,
                    timeout=5
                )
        print(f"Terminated processes using port {remote_port}")
    
    # Now try to kill by PID
    if server_pid:
        # Find all child processes recursively
        child_cmd = f"""
        children() {{
            local pid=$1
            local children=$(pgrep -P $pid 2>/dev/null)
            for child in $children; do
                children $child
                echo $child
            done
        }}
        children {server_pid} || echo ''
        """
        child_pids = run_ssh_command(
            remote_host,
            child_cmd,
            control_path,
            ssh_key,
            timeout=10
        )
        
        # Kill children first if any were found
        if child_pids and child_pids.strip():
            for child_pid in child_pids.strip().split('\n'):
                if child_pid.strip():
                    run_ssh_command(
                        remote_host,
                        f"kill -9 {child_pid.strip()} 2>/dev/null || true",
                        control_path,
                        ssh_key,
                        timeout=5
                    )
        
        # Kill the main process
        run_ssh_command(
            remote_host,
            f"kill -9 {server_pid} 2>/dev/null || true",
            control_path,
            ssh_key,
            timeout=5
        )
    
    # Final verification - kill any Python process using the port as a last resort
    run_ssh_command(
        remote_host,
        f"pkill -9 -f 'python.*{remote_port}' 2>/dev/null || true",
        control_path,
        ssh_key,
        timeout=5
    )
    
    print("Remote server processes terminated")

def main():
    """Main function"""
    args = parse_args()
    
    # Get the scripts directory
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get script paths
    server_script = os.path.join(scripts_dir, "remote_bridge_server.py")
    client_script = os.path.join(scripts_dir, "mcp_bridge_client.py")
    
    # Check if the scripts exist
    if not os.path.exists(server_script):
        print(f"Error: Bridge server script not found at {server_script}")
        return 1
    
    if not os.path.exists(client_script):
        print(f"Error: Bridge client script not found at {client_script}")
        return 1
    
    # Set up control master connection
    control_path = create_ssh_controlmaster(args.remote_host, args.ssh_key)
    if not control_path:
        print("Warning: Could not establish persistent SSH connection.")
        print("You may be prompted for your password multiple times.")
        control_path = None
        
    # Check if code-mcp is installed on the remote server and install it if needed
    if not check_and_install_code_mcp(args.remote_host, args.code_mcp_path, control_path, args.ssh_key):
        print("Warning: code-mcp was not found and automatic installation failed.")
        user_response = input("Do you want to continue anyway? (y/n): ").lower()
        if user_response != 'y':
            print("Setup aborted. Please install code-mcp on the remote server and try again.")
            return 1
    
    # Initialize variables
    tunnel_process = None
    server_pid = None
    remote_dir = None
    
    try:
        # Create a temporary directory on the remote host
        print("Creating temporary directory on remote host...")
        remote_dir = run_ssh_command(args.remote_host, "mktemp -d", control_path, args.ssh_key)
        if not remote_dir:
            print("Failed to create temporary directory on remote host")
            return 1
        
        # Upload the server script
        print(f"Uploading server script to {args.remote_host}:{remote_dir}...")
        if not run_scp_command(args.remote_host, server_script, f"{remote_dir}/remote_bridge_server.py", control_path, args.ssh_key):
            print("Failed to upload server script")
            return 1
        
        # Make the script executable
        run_ssh_command(args.remote_host, f"chmod +x {remote_dir}/remote_bridge_server.py", control_path, args.ssh_key)
        
        # First kill any existing processes on the port
        print(f"Ensuring port {args.remote_port} is free...")
        run_ssh_command(
            args.remote_host,
            f"lsof -i :{args.remote_port} | grep LISTEN | awk '{{print $2}}' | xargs -r kill -9",
            control_path,
            args.ssh_key,
            timeout=5
        )
        
        # Start the bridge server
        print(f"Starting bridge server on {args.remote_host}:{args.remote_port}...")
        
        # Modified approach: Use two separate commands
        # First command just starts the process in the background
        cmd = f"cd {remote_dir} && nohup python3 ./remote_bridge_server.py"
        cmd += f" --project-path {args.remote_project_path}"
        cmd += f" --port {args.remote_port}"
        cmd += f" --code-mcp-path {args.code_mcp_path}"
        
        if args.auth_token:
            cmd += f" --auth-token {args.auth_token}"
        
        # Start the server without waiting for PID output
        cmd += f" > {remote_dir}/bridge_server.log 2>&1 &"
        
        # Run the command without trying to capture PID
        try:
            run_ssh_command(args.remote_host, cmd, control_path, args.ssh_key, timeout=5)
            print("Bridge server started successfully")
            
            # Wait a moment for the process to start properly
            time.sleep(2)
            
            # Try to find PID separately after the process has started
            pid_cmd = f"lsof -i :{args.remote_port} | grep LISTEN | awk '{{print $2}}' | head -1"
            server_pid = run_ssh_command(args.remote_host, pid_cmd, control_path, args.ssh_key, timeout=5)
            
            if server_pid and server_pid.strip():
                print(f"Bridge server running with PID {server_pid}")
            else:
                print("Warning: Could not capture server PID but continuing anyway")
        except Exception as e:
            print(f"Error starting bridge server: {e}")
            print("Attempting to continue anyway...")
        
        # Wait a moment for the server to start
        time.sleep(2)
        
        # Verify the server is running by checking for listening port
        print("Verifying bridge server is running...")
        max_attempts = 3
        for attempt in range(max_attempts):
            check_cmd = f"lsof -i :{args.remote_port} | grep LISTEN || echo 'NOT_RUNNING'"
            verification = run_ssh_command(args.remote_host, check_cmd, control_path, args.ssh_key)
            
            if verification and "NOT_RUNNING" not in verification:
                print(f"Bridge server verified to be listening on port {args.remote_port}")
                break
            elif attempt < max_attempts - 1:
                print(f"Server not listening yet, waiting... (attempt {attempt+1}/{max_attempts})")
                time.sleep(2)
            else:
                print(f"Warning: Could not verify bridge server is running. Continuing anyway...")
        
        # Update Claude Desktop config
        update_claude_config(
            args.local_port, 
            args.remote_project_path,
            args.code_mcp_path,
            client_script,
            args.auth_token
        )
        
        # Create SSH tunnel
        tunnel_process = create_ssh_tunnel(
            args.remote_host, 
            args.local_port, 
            args.remote_port,
            control_path,
            args.ssh_key
        )
        
        if not tunnel_process:
            print("Failed to create SSH tunnel")
            return 1
        
        print("\nSetup complete!")
        print(f"Remote MCP bridge is running at http://localhost:{args.local_port}/bridge")
        print("\nPress Ctrl+C to stop the SSH tunnel and exit")
        
        # Define cleanup function
        def cleanup():
            print("\nCleaning up...")
            
            # Remove remote-code-mcp from Claude Desktop config
            print("Removing remote-code-mcp from Claude Desktop config...")
            try:
                config = read_claude_config()
                if "mcpServers" in config and "remote-code-mcp" in config["mcpServers"]:
                    del config["mcpServers"]["remote-code-mcp"]
                    write_claude_config(config)
                    print("Successfully removed remote-code-mcp from Claude Desktop config")
                else:
                    print("remote-code-mcp not found in Claude Desktop config")
            except Exception as e:
                print(f"Error removing remote-code-mcp from Claude Desktop config: {e}")
            
            # Kill the remote server process and all its children
            if server_pid or args.remote_port:
                kill_remote_processes(
                    args.remote_host, 
                    server_pid, 
                    args.remote_port, 
                    control_path, 
                    args.ssh_key
                )
            
            # Clean up remote directory if we know it
            if remote_dir:
                print(f"Cleaning up remote directory {remote_dir}...")
                run_ssh_command(
                    args.remote_host,
                    f"rm -rf {remote_dir}",
                    control_path,
                    args.ssh_key,
                    timeout=5
                )
            
            # Kill tunnel process if it exists
            if tunnel_process:
                kill_ssh_tunnel(tunnel_process)
                
            # Clean up control master if it exists
            if control_path:
                socket_dir = os.path.dirname(control_path)
                try:
                    # Close the control master
                    subprocess.run(
                        ["ssh", "-o", f"ControlPath={control_path}", "-O", "exit", args.remote_host],
                        check=False,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5  # Add timeout to prevent hanging
                    )
                    # Remove the temp directory
                    import shutil
                    shutil.rmtree(socket_dir, ignore_errors=True)
                except Exception as e:
                    print(f"Warning: Error cleaning up SSH control master: {e}")
            
            print("Cleanup complete")
        
        # Register cleanup function for normal exit
        atexit.register(cleanup)
        
        # Handle keyboard interrupt and termination signals
        def signal_handler(sig, frame):
            print("\nShutting down...")
            cleanup()
            # Exit directly instead of letting the program continue
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the script running to maintain the SSH tunnel
        while True:
            # Check if the tunnel is still running
            if tunnel_process.poll() is not None:
                print("SSH tunnel terminated unexpectedly")
                cleanup()  # Make sure we clean up if the tunnel dies
                return 1
            
            # Sleep a bit to reduce CPU usage
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down due to keyboard interrupt...")
        # The cleanup will be handled by the atexit handler
    except Exception as e:
        print(f"\nError: {e}")
        # Make sure to clean up even on unexpected errors
        if 'cleanup' in locals():
            cleanup()
        else:
            # Fallback cleanup if the main cleanup function isn't defined yet
            print("\nEmergency cleanup...")
            try:
                config = read_claude_config()
                if "mcpServers" in config and "remote-code-mcp" in config["mcpServers"]:
                    del config["mcpServers"]["remote-code-mcp"]
                    write_claude_config(config)
                    print("Successfully removed remote-code-mcp from Claude Desktop config")
            except Exception as e:
                print(f"Error removing remote-code-mcp from Claude Desktop config: {e}")
            
            
            if tunnel_process:
                kill_ssh_tunnel(tunnel_process)
            if server_pid or args.remote_port:
                # Kill any process using the port
                run_ssh_command(
                    args.remote_host,
                    f"lsof -i :{args.remote_port} | grep LISTEN | awk '{{print $2}}' | xargs -r kill -9",
                    control_path, 
                    args.ssh_key,
                    timeout=5
                )
                if server_pid:
                    run_ssh_command(
                        args.remote_host,
                        f"kill -9 {server_pid} 2>/dev/null || true",
                        control_path,
                        args.ssh_key,
                        timeout=5
                    )
            if remote_dir:
                run_ssh_command(args.remote_host, f"rm -rf {remote_dir}", control_path, args.ssh_key, timeout=5)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
