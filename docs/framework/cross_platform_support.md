# Cross-Platform Support

ThothCTL is designed to work seamlessly across different operating systems, with native support for Windows, Linux, and macOS.

## Platform Detection

ThothCTL automatically detects the operating system and adapts its behavior accordingly:

```python
from thothctl.utils.platform_utils import is_windows, is_linux, is_macos

# Automatic platform detection
if is_windows():
    print("Running on Windows")
elif is_linux():
    print("Running on Linux")
elif is_macos():
    print("Running on macOS")
```

## Windows Support

### Native Windows Integration

- **PowerShell Integration**: Native autocomplete support for PowerShell
- **Windows Paths**: Automatic handling of Windows path separators and formats
- **Executable Detection**: Automatic `.exe` extension handling for external tools
- **Configuration**: Windows-appropriate config directory (`%LOCALAPPDATA%\thothctl`)

### Supported Windows Versions

- Windows 10 (version 1903 and later)
- Windows 11 (all versions)
- Windows Server 2019 and later

### Shell Support

| Shell | Support Level | Autocomplete |
|-------|---------------|--------------|
| PowerShell 5.1+ | Full | ✅ Native |
| PowerShell Core 7+ | Full | ✅ Native |
| Command Prompt | Basic | ❌ Not supported |
| Git Bash | Basic | ❌ Not supported |

## Linux Support

### Distribution Support

ThothCTL works on all major Linux distributions:

- Ubuntu 18.04+
- Debian 10+
- CentOS 7+
- RHEL 7+
- Fedora 30+
- Arch Linux
- Alpine Linux

### Shell Support

| Shell | Support Level | Autocomplete |
|-------|---------------|--------------|
| Bash | Full | ✅ Native |
| Zsh | Full | ✅ Native |
| Fish | Full | ✅ Native |
| Dash | Basic | ❌ Not supported |

## macOS Support

### Version Support

- macOS 10.15 (Catalina) and later
- Apple Silicon (M1/M2) native support
- Intel-based Macs

### Shell Support

| Shell | Support Level | Autocomplete |
|-------|---------------|--------------|
| Bash | Full | ✅ Native |
| Zsh (default) | Full | ✅ Native |
| Fish | Full | ✅ Native |

## Path Handling

ThothCTL automatically handles platform-specific path formats:

### Windows
```powershell
# All these formats work
thothctl scan iac --directory .\terraform
thothctl scan iac --directory C:\projects\terraform
thothctl scan iac --directory \\server\share\terraform
```

### Unix (Linux/macOS)
```bash
# Standard Unix paths
thothctl scan iac --directory ./terraform
thothctl scan iac --directory /home/user/terraform
thothctl scan iac --directory ~/projects/terraform
```

## Configuration Directories

ThothCTL uses platform-appropriate configuration directories:

| Platform | Configuration Directory |
|----------|------------------------|
| Windows | `%LOCALAPPDATA%\thothctl` |
| Linux | `~/.thothcf` |
| macOS | `~/.thothcf` |

## External Tool Integration

ThothCTL automatically detects and integrates with external tools across platforms:

### Tool Detection

```python
# Automatic executable detection
terraform_path = find_executable("terraform")
# Windows: finds "terraform.exe"
# Unix: finds "terraform"
```

### Supported Tools

| Tool | Windows | Linux | macOS | Installation Method |
|------|---------|-------|-------|-------------------|
| Terraform | ✅ | ✅ | ✅ | Chocolatey, Direct download |
| OpenTofu | ✅ | ✅ | ✅ | Chocolatey, Package manager |
| Checkov | ✅ | ✅ | ✅ | pip install |
| Trivy | ✅ | ✅ | ✅ | Chocolatey, Package manager |
| Terraform-docs | ✅ | ✅ | ✅ | Chocolatey, Package manager |
| Terragrunt | ✅ | ✅ | ✅ | Direct download |

## Command Execution

ThothCTL adapts command execution based on the platform:

### Windows
- Uses `shell=True` for better PATH resolution
- Handles Windows-specific environment variables
- Supports both PowerShell and Command Prompt contexts

### Unix
- Direct process execution without shell
- Preserves Unix environment semantics
- Supports shell-specific features

## Environment Variables

Platform-specific environment variable handling:

### Common Variables
```bash
# Cross-platform
export THOTHCTL_DEBUG=true
export THOTH_LOG_LEVEL=DEBUG
```

### Windows-Specific
```powershell
# PowerShell
$env:THOTHCTL_DEBUG = "true"
$env:THOTH_CONFIG_DIR = "C:\custom\path"
```

### Unix-Specific
```bash
# Bash/Zsh
export THOTHCTL_DEBUG=true
export THOTH_CONFIG_DIR="/custom/path"
```

## Performance Considerations

### Windows
- Antivirus exclusions may be needed for optimal performance
- SSD storage recommended for large scans
- PowerShell execution policy may need adjustment

### Linux
- Standard Unix permissions apply
- Container environments fully supported
- Minimal resource overhead

### macOS
- Gatekeeper may require approval for external tools
- Homebrew integration for tool installation
- Apple Silicon native performance

## Development Environment

### Cross-Platform Development

ThothCTL supports development across all platforms:

```bash
# Clone and install (all platforms)
git clone https://github.com/thothforge/thothctl.git
cd thothctl
pip install -e .
```

### Platform-Specific Testing

```bash
# Run platform compatibility tests
python test_windows_compatibility.py  # Windows
python test_unix_compatibility.py     # Linux/macOS
```

## Migration Between Platforms

### Configuration Migration

Configuration files are portable between platforms:

1. Export configuration from source platform
2. Copy to target platform's config directory
3. Update any platform-specific paths

### Project Compatibility

ThothCTL projects are fully portable:
- Configuration files use relative paths
- Platform detection handles tool differences
- No platform-specific lock-in

## Best Practices

### Cross-Platform Projects

1. **Use relative paths** in configuration files
2. **Test on multiple platforms** during development
3. **Document platform-specific requirements**
4. **Use platform-agnostic tool versions**

### Platform-Specific Optimizations

#### Windows
- Use PowerShell for best experience
- Configure antivirus exclusions
- Use Chocolatey for tool management

#### Linux
- Use package managers for tool installation
- Consider container deployment
- Leverage shell scripting integration

#### macOS
- Use Homebrew for tool management
- Consider Apple Silicon compatibility
- Test with both Intel and ARM architectures

## Troubleshooting

For platform-specific issues, see:
- [Windows Troubleshooting](../troubleshooting/windows_troubleshooting.md)
- [Linux Troubleshooting](../troubleshooting/linux_troubleshooting.md)
- [macOS Troubleshooting](../troubleshooting/macos_troubleshooting.md)
