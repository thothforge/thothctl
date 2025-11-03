# Project Upgrade

The `thothctl project upgrade` command allows you to upgrade your project with the latest changes from a remote template repository. It provides intelligent comparison, conflict detection, and interactive file selection to ensure safe and controlled upgrades.

## Command Syntax

```bash
thothctl project upgrade [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-dr, --dry-run` | Show what changes would be made without applying them |
| `-i, --interactive` | Enable interactive mode for selective file updates |
| `-f, --force` | Force upgrade even when conflicts are detected |
| `--help` | Show help message and exit |

## Features

### Commit Hash Comparison

The upgrade command intelligently compares commit hashes between your local project and the remote template repository:

- **Up-to-date**: If commits match, no upgrade is needed
- **Behind**: Shows available updates when remote has newer commits
- **Ahead**: Warns when local project has commits not in remote

### File Change Detection

The command categorizes file changes into three types:

- **📄 NEW**: Files that don't exist locally but are present in the remote template
- **🔄 UPDATE**: Files that exist locally but have different content in the remote template
- **⚠️ CONFLICT**: Files that have been modified locally and also changed in the remote template

### Project-Specific File Exclusion

The upgrade process automatically excludes project-specific configuration files to prevent overwriting customizations:

- `.thothcf.toml` - Project configuration file
- `common/common.hcl` - Common Terragrunt configuration
- `common/common.tfvars` - Common Terraform variables
- `docs/catalog/catalog-info.yaml` - Backstage catalog information

## Usage Examples

### Dry Run Mode

Check what changes would be made without applying them:

```bash
# See what files would be updated
thothctl project upgrade --dry-run
```

Example output:
```
📊 Commit Comparison:
   Local:  abc123def (2024-01-15)
   Remote: xyz789ghi (2024-01-20)
   Status: Behind by 3 commits

📄 NEW files (2):
   - templates/new-component.tf
   - scripts/deploy.sh

🔄 UPDATE files (1):
   - README.md

⚠️ CONFLICT files (1):
   - main.tf (modified locally and in remote)
```

### Interactive Mode

Selectively choose which files to update:

```bash
# Enable interactive file selection
thothctl project upgrade --interactive
```

Interactive mode allows you to:
- Review each file change individually
- Choose which files to update
- Skip files you want to keep unchanged
- Handle conflicts manually

### Force Mode

Apply all changes, including conflicted files:

```bash
# Force upgrade all files
thothctl project upgrade --force
```

**⚠️ Warning**: Force mode will overwrite local changes in conflicted files. Use with caution.

### Combined Options

```bash
# Preview interactive selections
thothctl project upgrade --dry-run --interactive

# Force upgrade with interactive selection
thothctl project upgrade --interactive --force
```

## Upgrade Process

### 1. Repository Analysis

The command first analyzes both local and remote repositories:

```bash
# Clone remote template repository
git clone <template-repo-url> /tmp/template-repo

# Compare commit hashes
local_commit = git.Repo('.').head.commit
remote_commit = git.Repo('/tmp/template-repo').head.commit
```

### 2. File Comparison

For each file in the remote template:

1. **Check if file exists locally**
2. **Compare content if file exists**
3. **Categorize as NEW, UPDATE, or CONFLICT**
4. **Apply exclusion rules for project-specific files**

### 3. Change Application

Based on the selected mode:

- **Dry Run**: Display changes without applying
- **Interactive**: Prompt for each file selection
- **Standard**: Apply non-conflicted changes
- **Force**: Apply all changes including conflicts

## Best Practices

### Before Upgrading

1. **Commit Local Changes**: Ensure all local changes are committed
   ```bash
   git add .
   git commit -m "Save local changes before upgrade"
   ```

2. **Create Backup Branch**: Create a backup branch for safety
   ```bash
   git checkout -b backup-before-upgrade
   git checkout main
   ```

3. **Run Dry Run**: Always check what changes will be made
   ```bash
   thothctl project upgrade --dry-run
   ```

### During Upgrade

1. **Use Interactive Mode**: For better control over changes
   ```bash
   thothctl project upgrade --interactive
   ```

2. **Review Conflicts**: Carefully review conflicted files before applying
3. **Test Incrementally**: Apply changes in small batches when possible

### After Upgrade

1. **Test Functionality**: Ensure the project still works correctly
   ```bash
   # Run your project's test suite
   terraform plan  # for Terraform projects
   ```

2. **Commit Upgrade**: Commit the upgrade changes
   ```bash
   git add .
   git commit -m "chore: Upgrade project from template"
   ```

3. **Document Changes**: Update project documentation if needed

## Troubleshooting

### Common Issues

#### Path Corruption
If you encounter path corruption issues, ensure emoji prefixes are handled correctly:
- `📄 NEW: ` = 7 characters
- `🔄 UPDATE: ` = 10 characters

#### Git Authentication
Ensure proper git authentication for private repositories:
```bash
# Configure git credentials
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

#### Merge Conflicts
For complex conflicts, consider manual resolution:
```bash
# After upgrade, resolve conflicts manually
git status
git diff
# Edit conflicted files
git add .
git commit -m "resolve: Manual conflict resolution"
```

## Integration with CI/CD

### Automated Upgrade Checks

```yaml
# GitHub Actions example
name: Check Template Updates

on:
  schedule:
    - cron: '0 9 * * MON'  # Weekly on Monday
  workflow_dispatch:

jobs:
  check-updates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Check for updates
        run: |
          thothctl project upgrade --dry-run > upgrade-report.txt
          
      - name: Create Issue if Updates Available
        if: contains(steps.check.outputs.result, 'UPDATE') || contains(steps.check.outputs.result, 'NEW')
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Template Updates Available',
              body: 'New template updates are available. Run `thothctl project upgrade --dry-run` to see changes.'
            })
```

### Pull Request Workflow

```yaml
name: Template Upgrade PR

on:
  workflow_dispatch:
    inputs:
      upgrade_mode:
        description: 'Upgrade mode'
        required: true
        default: 'interactive'
        type: choice
        options:
          - dry-run
          - interactive
          - force

jobs:
  upgrade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Run Upgrade
        run: |
          git checkout -b template-upgrade-$(date +%Y%m%d)
          thothctl project upgrade --${{ github.event.inputs.upgrade_mode }}
          
      - name: Create Pull Request
        if: github.event.inputs.upgrade_mode != 'dry-run'
        uses: peter-evans/create-pull-request@v5
        with:
          title: 'chore: Upgrade project from template'
          body: |
            Automated template upgrade using ThothCTL.
            
            Please review the changes carefully before merging.
          branch: template-upgrade-$(date +%Y%m%d)
```

## Advanced Usage

### Custom Exclusion Patterns

While the command has built-in exclusions, you can extend them by modifying the upgrade service configuration in your project.

### Batch Processing

For multiple projects, create a script to upgrade them systematically:

```bash
#!/bin/bash
# upgrade-all-projects.sh

projects=("project1" "project2" "project3")

for project in "${projects[@]}"; do
    echo "Upgrading $project..."
    cd "$project"
    thothctl project upgrade --dry-run
    read -p "Proceed with upgrade? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        thothctl project upgrade --interactive
    fi
    cd ..
done
```

This upgrade functionality ensures your projects stay current with template improvements while maintaining control over which changes to apply.
