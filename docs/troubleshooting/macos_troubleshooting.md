# macOS Troubleshooting

## macOS-Specific Issues

### Installation Methods

#### Using Homebrew (Recommended)
```bash
# Install Python via Homebrew
brew install python

# Install ThothCTL
pip3 install thothctl
```

#### Using System Python
```bash
# Install using system Python
python3 -m pip install --user thothctl

# Add to PATH
echo 'export PATH=$PATH:~/Library/Python/3.x/bin' >> ~/.zshrc
source ~/.zshrc
```

### Common Issues

#### Command Not Found
```bash
# Check installation location
pip3 show -f thothctl

# Add to PATH
export PATH=$PATH:$(python3 -m site --user-base)/bin
```

#### Permission Denied
```bash
# Use user installation
pip3 install --user thothctl

# Or use virtual environment
python3 -m venv thothctl-env
source thothctl-env/bin/activate
pip install thothctl
```

### Dependencies

#### Graphviz Installation
```bash
# Using Homebrew
brew install graphviz

# Using MacPorts
sudo port install graphviz
```

#### Xcode Command Line Tools
```bash
# Install if needed
xcode-select --install
```

### Environment Setup

```bash
# Add to ~/.zshrc or ~/.bash_profile
export THOTHCTL_DEBUG=true
export THOTH_CONFIG_DIR=~/.thothcf
export PATH=$PATH:$(python3 -m site --user-base)/bin
```
