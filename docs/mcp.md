# ThothCTL MCP Integration

ThothCTL now supports the Model Context Protocol (MCP), allowing AI assistants like Amazon Q to interact with ThothCTL functionality directly.

## What is MCP?

Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## Setting Up MCP Server

### Starting the MCP Server

To start the ThothCTL MCP server:

```bash
thothctl mcp --port 8080
```

This will start the MCP server on port 8080 (default).

### Using the Convenience Script

Alternatively, you can use the provided convenience script:

```bash
./scripts/run_mcp_server.sh 8080
```

## Registering with Amazon Q

To use ThothCTL with Amazon Q, you need to register the MCP server with the Q CLI:

```bash
 q chat "List all ThothCTL projects using the MCP integration"
```

Once registered, you can interact with ThothCTL through Amazon Q using natural language.

## Example Interactions

With the MCP server running and registered with Amazon Q, you can use natural language to interact with ThothCTL:

- "List all projects managed by ThothCTL"
- "Scan my infrastructure code for security issues"
- "Generate IaC for my project"
- "Create an inventory of my infrastructure components"

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
