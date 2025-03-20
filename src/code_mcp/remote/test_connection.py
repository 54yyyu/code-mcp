#!/usr/bin/env python3
"""
Test Remote MCP Bridge Connection

A simple script to test the connection to a remote MCP bridge server.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Dict, Any

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_connection")

async def test_connection(bridge_url: str, timeout: int = 10) -> bool:
    """Test the connection to a remote MCP bridge server"""
    try:
        logger.info(f"Testing connection to {bridge_url}")
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Send a health check request
            health_url = bridge_url.replace("/bridge", "/health")
            response = await client.get(health_url)
            
            if response.status_code != 200:
                logger.error(f"Health check failed: {response.status_code} {response.text}")
                return False
            
            health_data = response.json()
            logger.info(f"Health check response: {health_data}")
            
            if health_data.get("status") != "ok":
                logger.error(f"Bridge server is not healthy: {health_data}")
                return False
            
            # Send a test tools/list request
            test_request = {
                "method": "tools/list",
                "serverPath": "code-mcp",
                "args": ["~/project"],
                "params": {}
            }
            
            logger.info("Sending tools/list request")
            response = await client.post(
                bridge_url,
                json=test_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Tools list request failed: {response.status_code} {response.text}")
                return False
            
            tools_response = response.json()
            
            if "error" in tools_response:
                logger.error(f"Error in tools response: {tools_response['error']}")
                return False
            
            logger.info(f"Successfully received tools list response")
            return True
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return False
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test Remote MCP Bridge Connection")
    parser.add_argument("--bridge-url", default="http://localhost:3000/bridge",
                      help="URL of the bridge server (default: http://localhost:3000/bridge)")
    parser.add_argument("--timeout", type=int, default=10,
                      help="Request timeout in seconds (default: 10)")
    
    args = parser.parse_args()
    
    # Test the connection
    if await test_connection(args.bridge_url, args.timeout):
        logger.info("Connection test successful! Remote MCP bridge is working.")
        return 0
    else:
        logger.error("Connection test failed. Please check your remote MCP bridge setup.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
