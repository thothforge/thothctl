# ThothForge Development Container

This development container provides a consistent environment for working with ThothForge tools and infrastructure as code.

## Included Tools

- **OpenTofu** - An open-source fork of Terraform for infrastructure as code
- **Terragrunt** - A thin wrapper for Terraform that provides extra tools for working with multiple Terraform modules
- **Terraform-docs** - A utility to generate documentation from Terraform modules
- **Checkov** - A static code analysis tool for infrastructure as code
- **Trivy** - A vulnerability scanner for containers and other artifacts
- **ThothCTL** - The ThothForge CLI tool for managing internal developer platform tasks
- **Python 3.10** - For running ThothCTL and other Python-based tools
- **Graphviz** - For generating diagrams
- **wkhtmltopdf** - For PDF generation

## Getting Started

1. Install [Visual Studio Code](https://code.visualstudio.com/)
2. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. Install [Docker](https://www.docker.com/products/docker-desktop/)
4. Clone this repository
5. Open the repository in VS Code
6. When prompted, click "Reopen in Container" or use the command palette (F1) and select "Dev Containers: Reopen in Container"

## Using the Container

Once inside the container, you can use all the included tools directly from the terminal:

```bash
# Use OpenTofu
tofu --version
# or use the alias
tf --version

# Use Terragrunt
terragrunt --version
# or use the alias
tg --version

# Use ThothCTL
thothctl --version

# Scan infrastructure code
checkov -d .
trivy fs .
```

## AWS Credentials

Your local AWS credentials are mounted into the container, so you can use AWS CLI and other AWS tools without additional configuration.

## Customizing

To add more tools or customize the environment, edit the `Dockerfile` and rebuild the container using the command palette: "Dev Containers: Rebuild Container".
