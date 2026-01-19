# ThothCTL MCP Integration

![ThothCTL MCP](./img/framework/thothfr.png)

ThothCTL supports the Model Context Protocol (MCP), allowing AI assistants like Kiro CLI (Amazon Q) to interact with ThothCTL functionality directly. This integration enhances developer productivity by enabling natural language interactions with your Internal Developer Platform.

## What is MCP?

Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## MCP Commands

ThothCTL provides several MCP-related commands:

```bash
thothctl mcp [OPTIONS] COMMAND [ARGS]...
```

Available commands:

- `server` - Start the MCP server for ThothCTL
- `register` - Register the MCP server with Amazon Q
- `status` - Check the status of the MCP server

For detailed documentation on each command, see the [MCP Command Documentation](./framework/commands/mcp/mcp.md).

### Starting the MCP Server

To start the ThothCTL MCP server:

```bash
thothctl mcp server -p 8080
```

This will start the MCP server on port 8080 (default).

### Registering with Kiro CLI

To use ThothCTL with Kiro CLI (Amazon Q), you need to register the MCP server:

```bash
kiro mcp add thothctl --command "thothctl mcp server"
```

Once registered, you can interact with ThothCTL through Kiro CLI using natural language:

```bash
kiro chat "List all ThothCTL projects using the MCP integration"
```

### Checking Server Status

To check if the MCP server is running:

```bash
thothctl mcp status
```

## Troubleshooting

### Common Issues

#### MCP Server Fails to Load

If you encounter an error like:

```
✗ thothctl has failed to load after 0.02 s
 - No such file or directory (os error 2)
 - run with Q_LOG_LEVEL=trace and see $TMPDIR/qchat for detail
```

This typically means one of the following:

1. **ThothCTL is not in your PATH**: Ensure that ThothCTL is properly installed and available in your system PATH.
   ```bash
   # Verify ThothCTL is in your PATH
   which thothctl
   
   # If not found, add it to your PATH or reinstall
   pip install --user thothctl
   ```

2. **MCP Server is not running**: Start the MCP server before using it with Amazon Q.
   ```bash
   # Start the MCP server in a separate terminal
   thothctl mcp server
   ```

3. **MCP configuration file is missing or corrupted**: Amazon Q Developer CLI stores MCP server configurations in JSON files.
   
   **Configuration file locations**:
   - Global Configuration: `~/.aws/amazonq/mcp.json` - Applies to all workspaces
   - Workspace Configuration: `.amazonq/mcp.json` - Specific to the current workspace
   
   The MCP configuration file should have this structure:
   ```json
   {
     "mcpServers": {
       "thothctl": {
         "command": "thothctl",
         "args": ["mcp", "server"],
         "env": {},
         "timeout": 60000
       }
     }
   }
   ```

   To recreate the configuration:
   ```bash
   q mcp remove thothctl
   q mcp add --name thothctl --command "thothctl" --args "mcp" --args "server"
   ```

For more detailed troubleshooting, see the [MCP Command Documentation](./framework/commands/mcp/mcp.md#troubleshooting).

## Example Interactions

With the MCP server running and registered with Amazon Q, you can use natural language to interact with ThothCTL:

- "List all projects managed by ThothCTL"
- "Scan my infrastructure code for security issues"
- "Generate IaC for my project"
- "Create an inventory of my infrastructure components"
- "Initialize a new project with ThothCTL"

## Available Tools

The MCP server exposes the following ThothCTL commands as tools:

### Project Management
- `thothctl_init_project` - Initialize and setup project configurations
- `thothctl_remove_project` - Remove a project managed by thothctl
- `thothctl_get_projects` - Get list of projects managed by thothctl

### Space Management
- `thothctl_init_space` - Initialize and setup space configurations
- `thothctl_remove_space` - Remove a space managed by thothctl
- `thothctl_get_spaces` - Get list of spaces managed by thothctl
- `thothctl_get_projects_in_space` - Get list of projects in a specific space

### Listing
- `thothctl_list_projects` - List projects managed by thothctl locally
- `thothctl_list_spaces` - List spaces managed by thothctl locally

### Infrastructure Management
- `thothctl_scan` - Scan infrastructure code for security issues
- `thothctl_inventory` - Create Inventory for the iac composition
- `thothctl_generate` - Generate IaC from rules, use cases, and components
- `thothctl_document` - Initialize and setup project documentation
- `thothctl_check` - Check infrastructure code for compliance
- `thothctl_project` - Convert, clean up and manage the current project

### Utility
- `thothctl_version` - Get ThothCTL version

## Architecture

The MCP server follows the HTTP-based MCP protocol:

1. The LLM requests available tools via a POST to `/tools`
2. The server responds with a list of available tools and their parameters
3. The LLM executes a tool via a POST to `/execute` with the tool name and parameters
4. The server executes the corresponding ThothCTL command and returns the results

## Space Management

The space management features allow you to:

- Create logical groupings of projects
- Share credentials and configurations across projects in the same space
- Maintain consistent version control, terraform, and orchestration settings
- Simplify management of related projects

## Security Considerations

The MCP server is designed to run locally and should not be exposed to the public internet. It does not implement authentication or encryption, as it's intended for local use only.

## Benefits of MCP Integration

- **Increased Developer Productivity**: Interact with ThothCTL using natural language
- **Simplified Workflows**: Combine multiple ThothCTL commands in a single request
- **Contextual Awareness**: AI assistants can understand the context of your projects
- **Reduced Learning Curve**: New team members can use ThothCTL without memorizing commands
- **Enhanced Collaboration**: Share complex ThothCTL workflows through natural language descriptions
