# MCP Command

Use this command to manage the Model Context Protocol (MCP) server for ThothCTL, which allows AI assistants like Amazon Q to interact with ThothCTL functionality.

```bash
thothctl mcp --help
Usage: thothctl mcp [OPTIONS] COMMAND [ARGS]...

  Model Context Protocol (MCP) server for ThothCTL

Options:
  --help  Show this message and exit.

Commands:
  register  Register the MCP server with Amazon Q.
  server    Start the MCP server for ThothCTL.
  status    Check the status of the MCP server.
```

## Overview

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). ThothCTL's MCP server enables AI assistants like Amazon Q to interact with ThothCTL functionality through natural language, enhancing developer productivity and simplifying complex workflows.

## ThothCTL MCP Server Command

### Overview

The `thothctl mcp server` command starts an MCP server that exposes ThothCTL functionality to AI assistants. This server acts as a bridge between the AI assistant and your local ThothCTL installation.

### Command Options

```bash
Usage: thothctl mcp server [OPTIONS]

  Start the MCP server for ThothCTL.

Options:
  -p, --port INTEGER  Port to run the MCP server on (default: 8080)
  --help              Show this message and exit.
```

### Example Usage

Start the MCP server on the default port (8080):

```bash
thothctl mcp server
```

Start the MCP server on a custom port:

```bash
thothctl mcp server -p 9090
```

## ThothCTL MCP Register Command

### Overview

The `thothctl mcp register` command registers the ThothCTL MCP server with Amazon Q, allowing you to use ThothCTL functionality through natural language queries.

### Command Options

```bash
Usage: thothctl mcp register [OPTIONS]

  Register the MCP server with Amazon Q.

Options:
  --port INTEGER  Port where the MCP server is running (default: 8080)
  --help         Show this message and exit.
```

### Example Usage

Register the MCP server running on the default port:

```bash
thothctl mcp register
```

This command will internally use the correct Amazon Q MCP registration syntax:

```bash
q mcp add --name thothctl --command "thothctl mcp server"
```

Register the MCP server running on a custom port:

```bash
thothctl mcp register --port 9090
```

## ThothCTL MCP Status Command

### Overview

The `thothctl mcp status` command checks if the MCP server is running and provides information about its status.

### Command Options

```bash
Usage: thothctl mcp status [OPTIONS]

  Check the status of the MCP server.

Options:
  --port INTEGER  Port to check for the MCP server (default: 8080)
  --help         Show this message and exit.
```

### Example Usage

Check the status of the MCP server on the default port:

```bash
thothctl mcp status
```

Check the status of the MCP server on a custom port:

```bash
thothctl mcp status --port 9090
```

## Available Tools (22)

The MCP server exposes the following ThothCTL commands as tools for AI assistants:

### Project Management
| Tool | Description |
|------|-------------|
| `thothctl_init_project` | Initialize a new project (terraform, tofu, cdkv2, terragrunt, custom) |
| `thothctl_remove_project` | Remove a project from local tracking |
| `thothctl_list_projects` | List all projects managed by thothctl |
| `thothctl_project_bootstrap` | Bootstrap existing projects with ThothCTL support |
| `thothctl_project_cleanup` | Clean up residual files and directories |
| `thothctl_project_convert` | Convert project to template or between formats |
| `thothctl_project_upgrade` | Upgrade project scaffold from remote template |

### Space Management
| Tool | Description |
|------|-------------|
| `thothctl_init_space` | Initialize a new space |
| `thothctl_remove_space` | Remove a space |
| `thothctl_list_spaces` | List all spaces |
| `thothctl_get_projects_in_space` | Get projects in a specific space |
| `thothctl_list_templates` | List available templates from VCS providers |

### Security & Compliance
| Tool | Description |
|------|-------------|
| `thothctl_scan_iac` | Scan IaC for security issues (Checkov, Trivy, KICS, OPA) |
| `thothctl_check_environment` | Check development environment tools |
| `thothctl_check_iac` | Check IaC artifacts (plans, structure) |
| `thothctl_check_project` | Validate project structure |

### Cost & Drift Analysis
| Tool | Description |
|------|-------------|
| `thothctl_cost_analysis` | Estimate AWS costs from Terraform plans or CloudFormation templates |
| `thothctl_drift_detection` | Detect infrastructure drift with tag filtering, policy enforcement, and AI analysis |

### AI-Powered Review
| Tool | Description |
|------|-------------|
| `thothctl_ai_review` | Multi-mode AI security analysis: analyze, decide, improve, orchestrate |

### Infrastructure Tooling
| Tool | Description |
|------|-------------|
| `thothctl_inventory_iac` | Create IaC composition inventory |
| `thothctl_document_iac` | Generate documentation for IaC projects |
| `thothctl_generate_stacks` | Generate infrastructure stacks |

### Utility
| Tool | Description |
|------|-------------|
| `thothctl_version` | Get ThothCTL version |
| `thothctl_upgrade` | Upgrade thothctl to latest version |

## Integration with Amazon Q

After starting the MCP server and registering it with Amazon Q, you can interact with ThothCTL using natural language:

```bash
q chat "List all ThothCTL projects"
```

Example interactions:

- "List all projects managed by ThothCTL"
- "Initialize a new Terraform project called my-vpc"
- "Create a Terragrunt project in the production space"
- "Initialize a CDK project with batch mode enabled"
- "Scan my infrastructure code for security issues"
- "Generate IaC for my project"
- "Create an inventory of my infrastructure components"

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

3. **Wrong command in registration**: Verify your registration command.
   ```bash
   # List your registered MCP servers
   q mcp list
   
   # Remove incorrect registration if needed
   q mcp remove thothctl
   
   # Register correctly
   q mcp add --name thothctl --command "thothctl mcp server"
   ```

4. **MCP configuration file is missing or corrupted**: Amazon Q Developer CLI stores MCP server configurations in JSON files.
   
   **Configuration file locations**:
   - Global Configuration: `~/.aws/amazonq/mcp.json` - Applies to all workspaces
   - Workspace Configuration: `.amazonq/mcp.json` - Specific to the current workspace
   
   ```bash
   # Check if the configuration files exist
   ls -la ~/.aws/amazonq/mcp.json  # Global config (Linux/macOS)
   ls -la .amazonq/mcp.json        # Workspace config (Linux/macOS)
   
   # View the current configuration
   cat ~/.aws/amazonq/mcp.json     # Global config (Linux/macOS)
   cat .amazonq/mcp.json           # Workspace config (Linux/macOS)
   
   # If missing or corrupted, recreate it
   q mcp remove thothctl
   q mcp add --name thothctl --command "thothctl mcp server"
   ```

   The MCP configuration file (`mcp.json`) should have the following structure:
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

   You can manually create or edit this file if needed, but it's recommended to use the `q mcp add` command to ensure proper formatting.

5. **Detailed debugging**: Run with increased logging as suggested in the error message.
   ```bash
   Q_LOG_LEVEL=trace q chat "List ThothCTL projects"
   
   # Then check the logs
   cat $TMPDIR/qchat/latest.log
   ```

#### Port Already in Use

If you see an error about the port being already in use:

```
Error: Address already in use
```

Try using a different port:

```bash
thothctl mcp server -p 8081
```

And update your registration accordingly:

```bash
q mcp remove thothctl
q mcp add --name thothctl --command "thothctl" --args "mcp" --args "server" --args "-p" --args "8081"
```

## Architecture

ThothCTL MCP exposes two server modes:

```
src/thothctl/services/mcp/
├── stdio_server.py          ← stdio mode (Kiro, Amazon Q, Claude Code, Copilot)
└── simple_http_server.py    ← HTTP mode (network integrations, CI/CD)
```

**Stdio mode** (`thothctl mcp server --stdio`):
- Used by AI coding assistants via MCP protocol over stdin/stdout
- Each tool maps to a subprocess call to the thothctl CLI
- 22 tools at full feature parity

**HTTP mode** (`thothctl mcp server -p 8080`):
- REST endpoints: `GET /tools`, `POST /execute`, `GET /health`
- CORS-enabled for browser/network integrations
- Same 22 tools via subprocess execution

## Security Considerations

The MCP server is designed to run locally and should not be exposed to the public internet. It does not implement authentication or encryption, as it's intended for local use only.

## Benefits of MCP Integration

- **Increased Developer Productivity**: Interact with ThothCTL using natural language
- **Simplified Workflows**: Combine multiple ThothCTL commands in a single request
- **Contextual Awareness**: AI assistants can understand the context of your projects
- **Reduced Learning Curve**: New team members can use ThothCTL without memorizing commands
- **Enhanced Collaboration**: Share complex ThothCTL workflows through natural language descriptions
