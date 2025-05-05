#!/bin/bash

# Run ThothCTL MCP Server
# This script starts the ThothCTL MCP server

PORT=${1:-8080}

echo "Starting ThothCTL MCP server on port $PORT"
thothctl mcp server --port $PORT
