FROM mcr.microsoft.com/devcontainers/python:3.10

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    graphviz \
    wkhtmltopdf \
    curl \
    unzip \
    git \
    jq \
    vim \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Install OpenTofu
RUN curl -Lo /tmp/opentofu.zip https://github.com/opentofu/opentofu/releases/download/v1.6.1/tofu_1.6.1_linux_amd64.zip \
    && unzip /tmp/opentofu.zip -d /tmp \
    && mv /tmp/tofu /usr/local/bin/ \
    && chmod +x /usr/local/bin/tofu \
    && rm /tmp/opentofu.zip

# Install Terragrunt
RUN curl -Lo /usr/local/bin/terragrunt https://github.com/gruntwork-io/terragrunt/releases/download/v0.55.0/terragrunt_linux_amd64 \
    && chmod +x /usr/local/bin/terragrunt

# Install terraform-docs
RUN curl -Lo /tmp/terraform-docs.tar.gz https://github.com/terraform-docs/terraform-docs/releases/download/v0.16.0/terraform-docs-v0.16.0-linux-amd64.tar.gz \
    && tar -xzf /tmp/terraform-docs.tar.gz -C /tmp \
    && mv /tmp/terraform-docs /usr/local/bin/ \
    && chmod +x /usr/local/bin/terraform-docs \
    && rm /tmp/terraform-docs.tar.gz

# Install Checkov
RUN pip install --no-cache-dir checkov

# Install Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin v0.48.0

# Install ThothCTL
RUN pip install --no-cache-dir thothctl

# Create a non-root user
USER vscode

# Set up aliases for common commands
RUN echo 'alias tf="tofu"' >> ~/.bashrc \
    && echo 'alias tg="terragrunt"' >> ~/.bashrc \
    && echo 'alias tfdocs="terraform-docs"' >> ~/.bashrc
