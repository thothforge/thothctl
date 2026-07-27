# ThothCTL Check Space Command

## Overview

The `thothctl check space` command provides comprehensive diagnostics for space configuration and setup. This command validates space configuration, VCS settings, credentials status, and project usage to help troubleshoot space-related issues.

## Command Structure

```
Usage: thothctl check space [OPTIONS]

  Check space configuration and diagnostics

Options:
  -s, --space-name TEXT    Name of the space to check [required]
  --help                   Show this message and exit.
```

## Basic Usage

### Check Space Configuration

```bash
thothctl check space --space-name development
```

This validates the specified space's configuration from the global `~/.thothcf/spaces.toml` registry and provides comprehensive diagnostics.

## Validation Output

The command provides professional Rich-formatted output with multiple diagnostic sections:

### Space Overview
- Space name and description
- Configuration status from `~/.thothcf/spaces.toml` (the global registry)
- Directory structure validation
- `configs/scan_policy.toml` existence check (space-level policy overrides)
- Creation and modification timestamps

### VCS Configuration
- Version control system provider (GitHub, Azure Repos, GitLab)
- Repository settings and authentication method
- Configuration file validation
- Connection status

### Credentials Status
- Authentication token availability
- Credential file locations
- Security status and recommendations
- Token expiration warnings (if applicable)

### Project Usage
- List of projects using this space
- Project count and status
- Space utilization metrics
- Project health indicators

## Example Output

```
ℹ️ 🔍 Checking space configuration: labvel-devsecops
                🌌 Space Overview: labvel-devsecops                 
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property         ┃ Value                                         ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Name             │ labvel-devsecops                              │
│ Version          │ 1.0.0                                         │
│ Path             │ /home/labvel/.thothcf/spaces/labvel-devsecops │
│ Config Path      │ configs                                       │
│ Credentials Path │ credentials                                   │
└──────────────────┴───────────────────────────────────────────────┘
                        🔄 VCS Configuration                         
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Setting             ┃ Value                       ┃ Status        ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Default Provider    │ github                      │ ✅ Configured │
│ Available Providers │ azure_repos, github, gitlab │ ✅ Set        │
│ VCS Path            │ vcs                         │ ✅ Set        │
└─────────────────────┴─────────────────────────────┴───────────────┘
                    🔒 Credentials Status                     
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Type      ┃ File          ┃ Status       ┃ Details         ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ VCS       │ vcs.enc       │ ✅ Available │ Size: 292 bytes │
│ TERRAFORM │ terraform.enc │ ❌ Missing   │ Not configured  │
│ CLOUD     │ cloud.enc     │ ❌ Missing   │ Not configured  │
└───────────┴───────────────┴──────────────┴─────────────────┘
╭────────────────────────────────────────────────────────────────────────────────────────────────────────── 📁 Projects ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ No projects are currently using space 'labvel-devsecops'                                                                                                                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Use Cases

### Space Troubleshooting

When experiencing issues with space configuration:

```bash
thothctl check space --space-name production
```

This helps identify:
- Missing configuration files
- Invalid VCS settings
- Credential issues
- Project association problems

### Pre-deployment Validation

Before deploying projects in a space:

```bash
thothctl check space --space-name staging
```

Ensures the space is properly configured and ready for project operations.

### Credential Verification

To verify credential setup and security:

```bash
thothctl check space --space-name development
```

Shows credential status and provides security recommendations.

## Configuration Validation

The command reads space configuration from `~/.thothcf/spaces.toml` — the single source of truth for all space definitions. It validates the space entry and its associated directory structure.

### Global Registry (`~/.thothcf/spaces.toml`)

The `check space` command looks up the space in the global registry:

```toml
[spaces.development]
name = "development"
description = "Development environment space"
created_at = "2024-01-15T10:30:00Z"

[spaces.development.version_control]
provider = "github"

[spaces.development.terraform]
registry = "https://registry.terraform.io"
auth_method = "token"

[spaces.development.orchestration]
tool = "terragrunt"

[spaces.development.projects]
[spaces.development.projects.my-app]
registered_at = "2024-01-16T09:00:00Z"
[spaces.development.projects.vpc-network]
registered_at = "2024-01-17T14:00:00Z"
```

### Space Directory Structure
```
~/.thothcf/spaces/{space_name}/
├── metadata.toml            # Directory identification (name, created_at, config_source)
├── configs/
│   └── scan_policy.toml     # Space-level scan policy overrides (optional)
├── credentials/             # Encrypted VCS/TF/cloud credentials
├── vcs/                     # VCS-specific settings
├── terraform/               # Terraform registry settings
└── orchestration/           # Orchestration tool settings
```

The command also checks for `configs/scan_policy.toml`, which provides space-level security policy overrides for scan operations.

Credentials are stored as encrypted `.enc` files in the `credentials/` directory. The `check space` command validates their presence and file integrity without decrypting them.

## Error Scenarios

### Space Not Found
```
❌ Space 'nonexistent' does not exist
```
**Solution**: Verify space name or create the space using `thothctl init space`.

### Missing Configuration
```
⚠️ Configuration file missing: metadata.toml
```
**Solution**: Reinitialize the space or manually create the metadata file.

### Invalid Credentials
```
❌ GitHub Token: Invalid or expired
```
**Solution**: Update credentials using space initialization or manual configuration.

### VCS Connection Issues
```
❌ VCS Configuration: Connection failed
```
**Solution**: Verify network connectivity and credential validity.

## Integration with Other Commands

### Space Initialization
```bash
# Create a new space
thothctl init space --space-name development --vcs-provider github

# Check the newly created space
thothctl check space --space-name development
```

### Project Creation
```bash
# Create project in space
thothctl init project --project-name my-app --space development

# Verify space configuration before project creation
thothctl check space --space-name development
```

### Space Management
```bash
# List all spaces
thothctl list spaces

# Check specific space
thothctl check space --space-name production

# Remove space (with validation)
thothctl remove space --space-name old-space
```

## Best Practices

1. **Regular Health Checks**: Run space checks periodically to ensure configuration integrity
2. **Pre-Project Validation**: Always check space configuration before creating new projects
3. **Credential Rotation**: Use space checks to monitor credential status and expiration
4. **Environment Consistency**: Validate space configuration across different environments
5. **Troubleshooting Workflow**: Use space checks as the first step in diagnosing space-related issues

## Troubleshooting

### Common Issues

#### Permission Denied
```
Error: [Errno 13] Permission denied: ~/.thothcf/spaces/development
```
**Solution**: Check file permissions and ensure proper access to the ThothCTL configuration directory.

#### Network Connectivity
```
❌ VCS Connection: Timeout
```
**Solution**: Verify network connectivity and firewall settings for VCS provider access.

#### Corrupted Configuration
```
⚠️ Configuration file corrupted
```
**Solution**: Backup and recreate the space configuration or restore from a known good state.

### Debugging

Enable debug mode for detailed diagnostic information:

```bash
thothctl --debug check space --space-name development
```

This provides:
- Detailed file system operations
- Network connection attempts
- Configuration parsing details
- Credential validation steps

## Exit Codes

- **Exit Code 0**: Space configuration is valid and healthy
- **Exit Code 1**: Space configuration issues detected or space not found

## Related Documentation

- [Space Configuration](../../space_configuration.md): Understanding ThothCTL spaces
- [Init Space Command](../init/init_space.md): Creating and configuring spaces
- [List Spaces Command](../list/list_spaces.md): Viewing available spaces
- [Remove Space Command](../remove/remove_space.md): Removing spaces safely
