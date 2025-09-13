# GitHub Template Integration

ThothCTL now automatically loads project templates from GitHub public repositories based on the project type. This provides standardized, up-to-date project scaffolding for different infrastructure frameworks.

## Default Behavior

When you run `thothctl init project`, the system will:

1. **Load from GitHub first**: Automatically clone the appropriate template repository based on project type
2. **Fallback to local templates**: If GitHub loading fails, use local hardcoded templates
3. **Apply template processing**: Replace placeholders and configure the project

## Supported Project Types and Templates

| Project Type | Default Repository |
|-------------|-------------------|
| `terragrunt` | https://github.com/thothforge/terragrunt_project_scaffold.git |
| `terraform` | https://github.com/thothforge/terraform_project_scaffold.git |
| `terraform_module` | https://github.com/thothforge/terraform_module_scaffold.git |
| `tofu` | https://github.com/thothforge/tofu_project_scaffold.git |
| `cdkv2` | https://github.com/thothforge/cdkv2_project_scaffold.git |

## Usage Examples

### Basic Project Creation
```bash
# Creates a terragrunt project using the GitHub template
thothctl init project --project-name my-infrastructure --project-type terragrunt

# Creates a terraform project using the GitHub template  
thothctl init project --project-name my-terraform --project-type terraform
```

### Managing Template Configurations

#### List Available Templates
```bash
# Show default GitHub templates
thothctl list templates

# Show templates from a specific space (VCS-based)
thothctl list templates --space my-space

# Show both default and VCS templates
thothctl list templates --space my-space --defaults
```

#### Set Custom Template Repository
```bash
thothctl init template --project-type terragrunt --template-url https://github.com/myorg/custom-terragrunt-template.git
```

#### View Current Template URL
```bash
thothctl init template --project-type terragrunt
```

## Configuration

Template URLs are stored in `~/.thothcf/.thothctl_templates.toml`:

```toml
[templates]
terragrunt = "https://github.com/myorg/custom-terragrunt-template.git"
terraform = "https://github.com/myorg/custom-terraform-template.git"
```

## Benefits

- **Always Up-to-Date**: Templates are fetched from the latest version in the repository
- **Standardized**: Consistent project structure across teams and organizations
- **Customizable**: Organizations can override default templates with their own
- **Fallback Safety**: Local templates ensure functionality even without internet access
- **Zero Configuration**: Works out of the box with sensible defaults

## Requirements

- Internet access for GitHub template loading
- Git installed on the system
- GitPython dependency (automatically installed with thothctl)

## Troubleshooting

If template loading fails:
1. Check internet connectivity
2. Verify the repository URL is accessible
3. The system will automatically fall back to local templates
4. Check logs with `--debug` flag for detailed error information
