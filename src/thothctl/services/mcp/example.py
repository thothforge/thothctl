"""Example usage of the ThothCTL MCP service."""

import asyncio
from .service import MCPService

async def run_mcp_service():
    """Run the MCP service."""
    # Create the service
    service = MCPService(host="localhost", port=8080)
    
    # Start the service
    await service.start()
    
    print("MCP service started on http://localhost:8080")
    print("Press Ctrl+C to stop the service")
    
    try:
        # Keep the service running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping MCP service...")
    finally:
        # Stop the service
        await service.stop()
        print("MCP service stopped")

if __name__ == "__main__":
    asyncio.run(run_mcp_service())
