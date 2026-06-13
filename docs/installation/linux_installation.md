# Linux & macOS Installation

## Prerequisites

- Python >= 3.8
- pip (included with Python)

```bash
python3 --version
```

## Install ThothCTL

```bash
pip install thothctl
```

Verify:

```bash
thothctl --version
```

## System Dependencies

### Graphviz (required for dependency graphs)

=== "Debian/Ubuntu"

    ```bash
    sudo apt install graphviz -y
    ```

=== "Fedora/RHEL"

    ```bash
    sudo dnf install graphviz -y
    ```

=== "macOS"

    ```bash
    brew install graphviz
    ```

### Optional Tools

Install based on your use case:

| Tool | Purpose | Install |
|------|---------|---------|
| Terraform / OpenTofu | IaC provisioning | [terraform.io](https://www.terraform.io/) / [opentofu.org](https://opentofu.org/) |
| Terragrunt | IaC orchestration | [terragrunt.gruntwork.io](https://terragrunt.gruntwork.io/) |
| Checkov | Security scanning | `pip install checkov` |
| Trivy | Vulnerability scanning | [trivy.dev](https://trivy.dev/latest/getting-started/installation/) |
| KICS | IaC security (Docker) | `docker pull checkmarx/kics:latest` |
| Terraform-docs | Module documentation | [terraform-docs.io](https://terraform-docs.io/) |

## Shell Autocomplete

```bash
thothctl-register-autocomplete
```

This detects your shell (Bash, Zsh, or Fish) and configures completion automatically.

### Manual Setup

=== "Bash"

    ```bash
    echo 'eval "$(_THOTHCTL_COMPLETE=bash_source thothctl)"' >> ~/.bashrc
    source ~/.bashrc
    ```

=== "Zsh"

    ```bash
    echo 'eval "$(_THOTHCTL_COMPLETE=zsh_source thothctl)"' >> ~/.zshrc
    source ~/.zshrc
    ```

=== "Fish"

    ```bash
    echo '_THOTHCTL_COMPLETE=fish_source thothctl | source' >> ~/.config/fish/config.fish
    ```

## Development Install

```bash
git clone https://github.com/thothforge/thothctl.git
cd thothctl
pip install -e .
```

## Next Steps

- [Quick Start](../quick_start.md)
- [Troubleshooting - Linux](../troubleshooting/linux_troubleshooting.md)
- [Troubleshooting - macOS](../troubleshooting/macos_troubleshooting.md)
