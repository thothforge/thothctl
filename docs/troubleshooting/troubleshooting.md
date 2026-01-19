# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### Python Version Compatibility
```bash
# Check Python version
python --version

# ThothCTL requires Python 3.8+
pip install --upgrade thothctl
```

#### Package Dependencies
```bash
# Install with all dependencies
pip install thothctl[all]

# Force reinstall if issues persist
pip install --force-reinstall thothctl
```

### Command Execution Issues

#### Permission Denied
```bash
# On Linux/macOS
chmod +x $(which thothctl)

# Or run with python
python -m thothctl --help
```

#### Module Not Found
```bash
# Ensure proper installation
pip show thothctl

# Reinstall if needed
pip uninstall thothctl
pip install thothctl
```

### Configuration Issues

#### Config File Not Found
```bash
# Initialize configuration
thothctl init --help

# Check config location
ls ~/.thothcf/
```

#### AWS Credentials
```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### Getting Help

For additional support:
- Check the [GitHub Issues](https://github.com/thothforge/thothctl/issues)
- Review command help: `thothctl <command> --help`
- Enable debug mode: `thothctl --debug <command>`
