# Windows Troubleshooting Guide

This guide covers common issues and solutions when using ThothCTL on Windows.

## Installation Issues

### Python Not Found

**Error**: `'python' is not recognized as an internal or external command`

**Solutions**:
1. Install Python from [python.org](https://www.python.org/downloads/)
2. Ensure "Add Python to PATH" is checked during installation
3. Or install via Chocolatey: `choco install python`

### Pip Not Found

**Error**: `'pip' is not recognized as an internal or external command`

**Solutions**:
```powershell
# Reinstall Python with pip
python -m ensurepip --upgrade

# Or use py launcher
py -m pip install thothctl
```

### Permission Denied During Installation

**Error**: `ERROR: Could not install packages due to an EnvironmentError: [WinError 5] Access is denied`

**Solutions**:
```powershell
# Install for current user only
pip install --user thothctl

# Or run PowerShell as Administrator
# Right-click PowerShell -> "Run as Administrator"
pip install thothctl
```

## Configuration Issues

### Config Directory Creation Failed

**Error**: Cannot create config directory in AppData

**Solutions**:
```powershell
# Manually create directory
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\thothctl"

# Check permissions
icacls "$env:LOCALAPPDATA\thothctl"

# Set custom config directory
$env:THOTH_CONFIG_DIR = "C:\thothctl-config"
```

### PowerShell Profile Issues

**Error**: Cannot modify PowerShell profile for autocomplete

**Solutions**:
```powershell
# Check if profile exists
Test-Path $PROFILE

# Create profile if missing
New-Item -ItemType File -Path $PROFILE -Force

# Set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## External Tool Issues

### Terraform Not Found

**Error**: `terraform.exe not found in PATH`

**Solutions**:
```powershell
# Install via Chocolatey
choco install terraform

# Or download from HashiCorp and add to PATH
# Add to PATH manually:
$env:Path += ";C:\path\to\terraform"

# Verify installation
terraform --version
```

### Checkov Not Found

**Error**: `checkov.exe not found in PATH`

**Solutions**:
```powershell
# Install via pip
pip install checkov

# Verify installation
checkov --version

# If still not found, check Scripts directory
where.exe checkov
```

### Trivy Not Found

**Error**: `trivy.exe not found in PATH`

**Solutions**:
```powershell
# Install via Chocolatey
choco install trivy

# Or download from GitHub releases
# Add to PATH manually

# Verify installation
trivy --version
```

## Command Execution Issues

### Shell Command Failures

**Error**: Commands fail with shell-related errors

**Solutions**:
```powershell
# Use PowerShell instead of Command Prompt
# Ensure you're using PowerShell 5.1 or later
$PSVersionTable.PSVersion

# Update PowerShell if needed
winget install Microsoft.PowerShell
```

### Path Separator Issues

**Error**: Commands fail with path-related errors

**Solutions**:
ThothCTL automatically handles Windows paths, but if issues persist:
```powershell
# Use forward slashes (works on Windows)
thothctl scan iac --directory ./terraform

# Or use backslashes with quotes
thothctl scan iac --directory ".\terraform"

# Or use absolute paths
thothctl scan iac --directory "C:\projects\terraform"
```

## Import and Module Issues

### Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'thothctl'`

**Solutions**:
```powershell
# Reinstall ThothCTL
pip uninstall thothctl
pip install thothctl

# Check Python path
python -c "import sys; print(sys.path)"

# Install in development mode if using source
pip install -e .
```

### Platform Detection Issues

**Error**: Platform-specific functionality not working

**Solutions**:
```powershell
# Test platform detection
python -c "from thothctl.utils.platform_utils import is_windows; print(is_windows())"

# Should return: True

# Run compatibility test
python test_windows_compatibility.py
```

## Performance Issues

### Slow Command Execution

**Issue**: Commands take longer than expected

**Solutions**:
```powershell
# Disable Windows Defender real-time scanning for development folders
# Add exclusion for your project directory

# Use SSD storage for better I/O performance

# Close unnecessary applications

# Enable debug mode to identify bottlenecks
$env:THOTHCTL_DEBUG = "true"
thothctl scan iac --directory .\terraform
```

### Memory Issues

**Issue**: Out of memory errors during large scans

**Solutions**:
```powershell
# Increase virtual memory (pagefile)
# Scan smaller directories at a time
# Close other applications

# Monitor memory usage
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10
```

## Network and Proxy Issues

### Proxy Configuration

**Issue**: Cannot download packages or connect to registries

**Solutions**:
```powershell
# Configure pip proxy
pip install --proxy http://proxy.company.com:8080 thothctl

# Set environment variables
$env:HTTP_PROXY = "http://proxy.company.com:8080"
$env:HTTPS_PROXY = "http://proxy.company.com:8080"

# Configure git proxy (if using git features)
git config --global http.proxy http://proxy.company.com:8080
```

## Antivirus and Security Issues

### Windows Defender Blocking

**Issue**: Windows Defender blocks ThothCTL execution

**Solutions**:
```powershell
# Add exclusion for Python Scripts directory
# Windows Security -> Virus & threat protection -> Exclusions
# Add: %LOCALAPPDATA%\Programs\Python\Python3XX\Scripts

# Add exclusion for project directories
# Add: C:\your\project\directory
```

### Execution Policy Issues

**Issue**: PowerShell execution policy prevents script execution

**Solutions**:
```powershell
# Check current policy
Get-ExecutionPolicy

# Set policy for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or bypass for single session
powershell -ExecutionPolicy Bypass -File script.ps1
```

## Debugging Commands

### Enable Debug Mode

```powershell
# Enable debug logging
$env:THOTHCTL_DEBUG = "true"

# Enable verbose logging
$env:THOTHCTL_VERBOSE = "true"

# Set log level
$env:THOTH_LOG_LEVEL = "DEBUG"

# Run command with debug info
thothctl scan iac --directory .\terraform
```

### Check System Information

```powershell
# Check Windows version
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion

# Check PowerShell version
$PSVersionTable

# Check Python version and location
python --version
where.exe python

# Check installed packages
pip list | findstr thothctl

# Check PATH
$env:Path -split ';' | Where-Object { $_ -like "*python*" }
```

### Test Platform Utilities

```powershell
# Test platform detection
python -c "
from thothctl.utils.platform_utils import *
print(f'Windows: {is_windows()}')
print(f'Config dir: {get_config_dir()}')
print(f'Terraform exe: {get_executable_name(\"terraform\")}')
print(f'Found terraform: {find_executable(\"terraform\")}')
"
```

## Getting Help

### Log Files

ThothCTL logs are typically stored in:
```
%LOCALAPPDATA%\thothctl\logs\
```

### System Information for Bug Reports

When reporting issues, include:

```powershell
# System info
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"

# Python info
python --version
pip --version

# ThothCTL info
thothctl --version

# Installed packages
pip list | findstr -E "(thothctl|checkov|trivy)"

# PATH info
echo $env:Path
```

### Community Support

- [GitHub Issues](https://github.com/thothforge/thothctl/issues)
- [Documentation](https://thothforge.github.io/thothctl/)
- [Discord Community](https://discord.gg/thothforge)

## Advanced Troubleshooting

### Clean Installation

If all else fails, perform a clean installation:

```powershell
# Uninstall ThothCTL
pip uninstall thothctl

# Clear pip cache
pip cache purge

# Remove config directory
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\thothctl"

# Reinstall
pip install thothctl

# Verify installation
python test_windows_compatibility.py
```

### Virtual Environment

Use a virtual environment to isolate dependencies:

```powershell
# Create virtual environment
python -m venv thothctl-env

# Activate environment
.\thothctl-env\Scripts\Activate.ps1

# Install ThothCTL
pip install thothctl

# Use ThothCTL
thothctl --version
```
