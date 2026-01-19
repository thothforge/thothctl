# Linux Troubleshooting

## Linux-Specific Issues

### Package Manager Issues

#### Ubuntu/Debian
```bash
# Update package lists
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip

# Install ThothCTL
pip3 install thothctl
```

#### CentOS/RHEL/Fedora
```bash
# Install Python and pip
sudo yum install python3 python3-pip
# or for newer versions
sudo dnf install python3 python3-pip

# Install ThothCTL
pip3 install thothctl
```

### Permission Issues

#### User Installation
```bash
# Install for current user only
pip3 install --user thothctl

# Add to PATH
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
source ~/.bashrc
```

#### System-wide Installation
```bash
# Install system-wide (requires sudo)
sudo pip3 install thothctl
```

### Dependencies

#### Graphviz Installation
```bash
# Ubuntu/Debian
sudo apt install graphviz

# CentOS/RHEL/Fedora
sudo yum install graphviz
# or
sudo dnf install graphviz
```

### Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export THOTHCTL_DEBUG=true
export THOTH_CONFIG_DIR=~/.thothcf
```
