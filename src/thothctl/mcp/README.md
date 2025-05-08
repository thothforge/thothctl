# ThothCTL MCP Server

This module provides a Model Context Protocol (MCP) server for ThothCTL, allowing AI assistants like Amazon Q to interact with ThothCTL functionality.

## What is MCP?

Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## Usage

To start the MCP server:

```bash
thothctl mcp --port 8080
```

This will start the MCP server on port 8080 (default).

## Registering with Amazon Q

To use ThothCTL with Amazon Q, you need to register the MCP server with the Q CLI:

```bash
q mcp add thothctl http://localhost:8080
```

## Available Tools

The MCP server exposes the following ThothCTL commands as tools:

- `thothctl_init` - Initialize and setup project configurations
- `thothctl_list` - List Projects managed by thothctl locally
- `thothctl_scan` - Scan infrastructure code for security issues
- `thothctl_inventory` - Create Inventory for the iac composition
- `thothctl_generate` - Generate IaC from rules, use cases, and components
- `thothctl_document` - Initialize and setup project documentation
- `thothctl_check` - Check infrastructure code for compliance
- `thothctl_project` - Convert, clean up and manage the current project
- `thothctl_remove` - Remove Projects managed by thothctl
- `thothctl_get_projects` - Get list of projects managed by thothctl
- `thothctl_version` - Get ThothCTL version

## Architecture

The MCP server follows the HTTP-based MCP protocol:

1. The LLM requests available tools via a POST to `/tools`
2. The server responds with a list of available tools and their parameters
3. The LLM executes a tool via a POST to `/execute` with the tool name and parameters
4. The server executes the corresponding ThothCTL command and returns the results

## Security Considerations

The MCP server is designed to run locally and should not be exposed to the public internet. It does not implement authentication or encryption, as it's intended for local use only.
