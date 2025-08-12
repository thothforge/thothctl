# Project Cleanup

The `thothctl project cleanup` command helps you maintain clean and organized projects by removing residual files and directories that are not needed for the project's operation. This includes temporary files, build artifacts, and other unnecessary items that can clutter your project.

## Command Syntax

```bash
thothctl project cleanup [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-cfd, --clean-additional-folders TEXT` | Add folders to clean, specified as a comma-separated list (e.g., `-cfd folder_1,folder_2`) |
| `-cfs, --clean-additional-files TEXT` | Add files to clean, specified as a comma-separated list (e.g., `-cfs file_1,file_2`) |
| `--help` | Show help message and exit |

## Default Cleanup Behavior

By default, the `project cleanup` command removes common temporary files and directories that are typically not needed in a clean project, such as:

- `.terraform` directories (Terraform cache)
- `.terragrunt-cache` directories (Terragrunt cache)
- `.terraform.lock.hcl` files (Terraform dependency locks)
- `terraform.tfstate` and `terraform.tfstate.backup` files (local state files)
- `.DS_Store` files (macOS metadata)
- `__pycache__` directories (Python bytecode cache)
- `.pytest_cache` directories (pytest cache)
- Various log files and temporary files

## Custom Cleanup

You can extend the default cleanup behavior by specifying additional files and directories to remove:

### Cleaning Additional Folders

```bash
# Clean up default items plus custom folders
thothctl project cleanup --clean-additional-folders node_modules,dist,build

# Clean up multiple specific folders
thothctl project cleanup -cfd logs,temp,output
```

### Cleaning Additional Files

```bash
# Clean up default items plus custom files
thothctl project cleanup --clean-additional-files config.local.json,secrets.txt

# Clean up multiple specific files
thothctl project cleanup -cfs *.log,*.tmp,*.bak
```
![./img/clean_project](clean%20project%20img)


### Combining Options

You can combine both options to clean up both additional folders and files:

```bash
# Clean up custom folders and files
thothctl project cleanup -cfd node_modules,dist -cfs *.log,*.tmp
```

## Examples

### Basic Cleanup

```bash
# Navigate to your project directory
cd my-project

# Run basic cleanup
thothctl project cleanup
```

### Cleaning Terraform-related Files

```bash
# Clean up Terraform-specific files and directories
thothctl project cleanup -cfd .terraform,.terragrunt-cache -cfs terraform.tfstate,terraform.tfstate.backup,.terraform.lock.hcl
```

### Cleaning Build Artifacts

```bash
# Clean up build artifacts
thothctl project cleanup -cfd build,dist,target -cfs *.jar,*.war,*.class
```

### Cleaning Temporary Files

```bash
# Clean up temporary files
thothctl project cleanup -cfs *.tmp,*.temp,*.bak,*.swp
```

## Best Practices

1. **Version Control**: Always commit important changes before running cleanup to avoid losing work
2. **Gitignore**: Use `.gitignore` files to prevent committing temporary files rather than cleaning them repeatedly
3. **Regular Cleanup**: Incorporate cleanup into your regular workflow to keep projects tidy
4. **Verify Before Cleaning**: Review what will be cleaned before running the command on important projects
5. **Project-specific Cleanup**: Create project-specific cleanup scripts for recurring cleanup tasks

## Integration with Development Workflow

### Pre-commit Hook

You can add a cleanup step to your pre-commit hook to ensure your commits don't include unnecessary files:

```bash
# Create a pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "Cleaning up project..."
thothctl project cleanup
git add .
EOF
chmod +x .git/hooks/pre-commit
```

### CI/CD Pipeline

You can include cleanup in your CI/CD pipeline to ensure clean builds:

```yaml
# GitHub Actions example
name: Build and Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install thothctl
          
      - name: Clean up project
        run: thothctl project cleanup
        
      - name: Build and test
        run: |
          # Your build and test commands here
```

## Common Use Cases

### Preparing for Deployment

Clean up unnecessary files before deploying to reduce package size:

```bash
# Clean up before packaging
thothctl project cleanup
# Package the application
tar -czf app.tar.gz .
```

### Freeing Disk Space

Remove large temporary directories to free up disk space:

```bash
# Clean up large directories
thothctl project cleanup -cfd node_modules,.terraform,target
```

### Preparing for Code Review

Clean up before submitting code for review to focus on relevant changes:

```bash
# Clean up before creating a pull request
thothctl project cleanup
git add .
git commit -m "feat: Add new feature"
git push
```

### Troubleshooting

Clean up cached files when troubleshooting build or runtime issues:

```bash
# Clean up caches to start fresh
thothctl project cleanup
# Rebuild the project
./build.sh
```
