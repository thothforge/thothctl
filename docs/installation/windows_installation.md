# Windows Installation Guide

ThothCTL fully supports Windows 10 and Windows 11 with native PowerShell integration.

## Prerequisites

### Required Software

1. **Python 3.8 or higher**
   ```powershell
   # Check Python version
   python --version
   ```
   
   If Python is not installed, download from [python.org](https://www.python.org/downloads/) or install via Chocolatey:
   ```powershell
   choco install python
   ```

2. **Git** (optional, for version control features)
   ```powershell
   choco install git
   ```

3. **Graphviz** (optional, for dependency graphs)
   ```powershell
   choco install graphviz
   ```

### External Tools (Optional)

Install these tools based on your use case:

- **Terraform/OpenTofu**: For IaC operations
  ```powershell
  choco install terraform
  # or
  choco install opentofu
  ```

- **Checkov**: For security scanning
  ```powershell
  pip install checkov
  ```

- **Trivy**: For vulnerability scanning
  ```powershell
  choco install trivy
  ```

- **Terraform-docs**: For documentation generation
  ```powershell
  choco install terraform-docs
  ```

## Installation

### Install from PyPI

```powershell
# Install ThothCTL
pip install thothctl

# Verify installation
thothctl --version
```

### Install from Source

```powershell
# Clone repository
git clone https://github.com/thothforge/thothctl.git
cd thothctl

# Install in development mode
pip install -e .

# Verify installation
thothctl --version
```

## Configuration

### PowerShell Autocomplete

Enable command autocompletion in PowerShell:

```powershell
# Run the autocomplete setup
thothctl-register-autocomplete

# Follow the prompts to add to your PowerShell profile
```

Alternatively, manually add to your PowerShell profile:

```powershell
# Open PowerShell profile
notepad $PROFILE

# Add this line:
Register-ArgumentCompleter -Native -CommandName thothctl -ScriptBlock { param($wordToComplete, $commandAst, $cursorPosition); $env:_THOTHCTL_COMPLETE="powershell_complete"; $env:COMP_WORDS=$commandAst.ToString(); $env:COMP_CWORD=$cursorPosition; thothctl 2>$null }

# Reload profile
. $PROFILE
```

### Configuration Directory

ThothCTL stores configuration in:
```
%LOCALAPPDATA%\thothctl
```

Typically: `C:\Users\<YourUsername>\AppData\Local\thothctl`

## Verify Installation

Run the Windows compatibility test:

```powershell
# Download and run the test script
python test_windows_compatibility.py
```

Expected output:
```
🪟 ThothCTL Windows Compatibility Test
========================================
🔍 Testing platform detection...
   Platform: Windows
   is_windows(): True
   Config dir: C:\Users\...\AppData\Local\thothctl
   Executable name (terraform): terraform.exe
   ✅ Platform detection works

📦 Testing imports...
   ✅ CLI UI imports work
   ✅ Common imports work
   ✅ Scanner imports work

📁 Testing config directory...
   Config directory: C:\Users\...\AppData\Local\thothctl
   ✅ Config directory created successfully

🔧 Testing autocomplete...
   ✅ Autocomplete module imports successfully
   💡 Run 'thothctl-register-autocomplete' to set up PowerShell completion

========================================
📊 Results: 4/4 tests passed
🎉 All tests passed! ThothCTL should work on Windows.
```

## Quick Start

### Initialize a Space

```powershell
# Create a new space
thothctl init space -s my-space -ot terragrunt -vcs github

# Verify space creation
thothctl list spaces
```

### Initialize a Project

```powershell
# Create a new project
thothctl init project -p my-project -s my-space

# Navigate to project
cd my-project
```

### Scan Infrastructure

```powershell
# Scan Terraform code
thothctl scan iac --directory .\terraform

# Scan with specific tools
thothctl scan iac --directory .\terraform --tools checkov,trivy
```

### Create Inventory

```powershell
# Generate inventory with version checking
thothctl inventory iac --check-versions

# Generate HTML report
thothctl inventory iac --check-versions --report-type html
```

## Common Issues

### Issue: Command Not Found

**Problem**: `thothctl` command not recognized

**Solution**:
```powershell
# Ensure Python Scripts directory is in PATH
$env:Path += ";$env:LOCALAPPDATA\Programs\Python\Python3XX\Scripts"

# Or reinstall with --user flag
pip install --user thothctl
```

### Issue: External Tool Not Found

**Problem**: "terraform.exe not found in PATH"

**Solution**:
```powershell
# Verify tool is installed
where.exe terraform

# If not found, install via Chocolatey
choco install terraform

# Refresh environment variables
refreshenv
```

### Issue: Permission Denied

**Problem**: Cannot create config directory

**Solution**:
```powershell
# Run PowerShell as Administrator
# Or manually create directory
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\thothctl"
```

### Issue: Import Errors

**Problem**: Module import failures

**Solution**:
```powershell
# Reinstall with all dependencies
pip uninstall thothctl
pip install thothctl

# Or install from source
pip install -e .
```

## Path Handling

ThothCTL automatically handles Windows path formats:

```powershell
# All these work correctly
thothctl scan iac --directory .\terraform
thothctl scan iac --directory C:\projects\terraform
thothctl scan iac --directory \\network\share\terraform
```

## Environment Variables

Set environment variables for ThothCTL:

```powershell
# Enable debug mode
$env:THOTHCTL_DEBUG = "true"

# Set custom config directory
$env:THOTH_CONFIG_DIR = "C:\custom\path"

# Set log level
$env:THOTH_LOG_LEVEL = "DEBUG"
```

## Next Steps

- [Quick Start Guide](../quick_start.md)
- [Command Reference](../index.md#commands)
- [Use Cases](../framework/use_cases/README.md)
- [MCP Integration](../mcp.md)

## Support

For Windows-specific issues:
- Check [GitHub Issues](https://github.com/thothforge/thothctl/issues)
- Review [Troubleshooting Guide](../troubleshooting/windows_troubleshooting.md)
- Join community discussions
