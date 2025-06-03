# Document Command Use Cases

The `thothctl document` command is designed to support various documentation use cases for infrastructure teams and developers. This page outlines common use cases and how to implement them using ThothCTL.

## Terraform Module Documentation

Generate comprehensive documentation for Terraform modules to make them more usable and maintainable.

```bash
# Navigate to your Terraform module directory
cd my-terraform-module

# Generate documentation
thothctl document iac -f terraform

# The documentation will be generated in README.md by default
```

This creates standardized documentation that includes:
- Module inputs (variables)
- Module outputs
- Required providers
- Resources created
- Usage examples

## Multi-Module Repository Documentation

For repositories containing multiple Terraform modules, you can generate documentation for all modules at once.

```bash
# Navigate to the repository root
cd terraform-modules-repo

# Generate documentation recursively for all modules
thothctl document iac -f terraform --recursive

# Exclude test directories and examples
thothctl document iac -f terraform --recursive --exclude "**/tests/**" --exclude "**/examples/**"
```

## Terragrunt Project Documentation

Generate documentation for Terragrunt projects to document the infrastructure components and their relationships.

```bash
# Navigate to your Terragrunt project directory
cd my-terragrunt-project

# Generate documentation
thothctl document iac -f terragrunt

# For projects with a specific suffix pattern
thothctl document iac -f terragrunt --suffix "-infra"
```

## Documentation as Part of CI/CD

Integrate documentation generation into your CI/CD pipeline to ensure documentation stays up-to-date with code changes.

### GitHub Actions Example

```yaml
name: Update Documentation

on:
  pull_request:
    paths:
      - '**.tf'
      - '**.hcl'

jobs:
  update-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.head_ref }}
          
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Generate Documentation
        run: thothctl document iac -f terraform --recursive
        
      - name: Check for changes
        id: git-check
        run: |
          git diff --exit-code || echo "changes=true" >> $GITHUB_OUTPUT
          
      - name: Commit changes if needed
        if: steps.git-check.outputs.changes == 'true'
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add README.md **/README.md
          git commit -m "docs: Update generated documentation"
          git push
```

## Custom Documentation Templates

Use custom templates to generate documentation that matches your organization's standards.

```bash
# Create a custom terraform-docs configuration file
cat > terraform-docs.yml << 'EOF'
formatter: markdown table

header-from: main.tf
footer-from: ""

sections:
  hide: []
  show: []

content: |-
  {{ .Header }}
  
  ## Overview
  
  This module is part of the ACME Corporation infrastructure.
  
  ## Usage
  
  ```hcl
  module "example" {
    source = "git::https://github.com/acme/terraform-modules.git//modules/{{ .Name }}"
    
    // Required variables
    region = "us-west-2"
  }
  ```
  
  {{ .Requirements }}
  
  {{ .Providers }}
  
  {{ .Resources }}
  
  {{ .Inputs }}
  
  {{ .Outputs }}
  
  ## Support
  
  For support, contact the infrastructure team at infra@acme.com.

output:
  file: "README.md"
  mode: replace
EOF

# Generate documentation using the custom configuration
thothctl document iac -f terraform --config-file terraform-docs.yml
```

## Documentation for Compliance

Generate documentation to demonstrate compliance with organizational standards or regulatory requirements.

```bash
# Create a custom configuration that highlights compliance-related resources
cat > compliance-docs.yml << 'EOF'
formatter: markdown table

sections:
  hide: []
  show: []

content: |-
  # Compliance Documentation
  
  This document outlines the compliance-related resources in this module.
  
  ## Security Controls
  
  {{ range .Resources }}
  {{ if contains .Type "aws_kms" "aws_iam" "aws_security_group" }}
  ### {{ .Name }}
  
  Type: {{ .Type }}
  
  {{ end }}
  {{ end }}
  
  ## Data Protection
  
  {{ range .Resources }}
  {{ if contains .Type "aws_s3_bucket" "aws_dynamodb_table" "aws_rds_cluster" }}
  ### {{ .Name }}
  
  Type: {{ .Type }}
  
  {{ end }}
  {{ end }}

output:
  file: "COMPLIANCE.md"
  mode: replace
EOF

# Generate compliance documentation
thothctl document iac -f terraform --config-file compliance-docs.yml
```

## Documentation for Different Audiences

Generate different types of documentation for different audiences.

```bash
# For developers - detailed technical documentation
thothctl document iac -f terraform --config-file developer-docs.yml

# For operators - operational documentation
thothctl document iac -f terraform --config-file operator-docs.yml

# For executives - high-level overview
thothctl document iac -f terraform --config-file executive-docs.yml
```

## Documentation for Onboarding

Generate documentation to help new team members understand the infrastructure.

```bash
# Create a custom configuration focused on onboarding
cat > onboarding-docs.yml << 'EOF'
formatter: markdown table

content: |-
  # Onboarding Guide: {{ .Name }}
  
  ## Overview
  
  {{ .Header }}
  
  ## Architecture
  
  This module is part of the following architecture:
  
  - Region: {{ .Inputs.region.Default | default "us-west-2" }}
  - Environment: {{ .Inputs.environment.Default | default "dev" }}
  
  ## Key Resources
  
  {{ range .Resources }}
  - {{ .Type }}: {{ .Name }}
  {{ end }}
  
  ## How to Deploy
  
  ```bash
  terraform init
  terraform plan
  terraform apply
  ```
  
  ## Common Tasks
  
  - How to update: Run `terraform apply` after changing variables
  - How to destroy: Run `terraform destroy`
  - How to troubleshoot: Check CloudWatch logs

output:
  file: "ONBOARDING.md"
  mode: replace
EOF

# Generate onboarding documentation
thothctl document iac -f terraform --config-file onboarding-docs.yml
```

## Documentation for Migration

Generate documentation to assist with infrastructure migrations.

```bash
# Create a custom configuration focused on migration
cat > migration-docs.yml << 'EOF'
formatter: markdown table

content: |-
  # Migration Guide: {{ .Name }}
  
  ## Current Resources
  
  {{ range .Resources }}
  - {{ .Type }}: {{ .Name }}
  {{ end }}
  
  ## Migration Steps
  
  1. Back up any data from existing resources
  2. Apply the new Terraform configuration
  3. Validate the new resources
  4. Migrate data if necessary
  5. Update DNS or other references
  6. Decommission old resources

output:
  file: "MIGRATION.md"
  mode: replace
EOF

# Generate migration documentation
thothctl document iac -f terraform --config-file migration-docs.yml
```

## Documentation for Architecture Decision Records

Generate documentation to capture architecture decisions.

```bash
# Create a custom configuration for ADRs
cat > adr-docs.yml << 'EOF'
formatter: markdown table

content: |-
  # Architecture Decision Record: {{ .Name }}
  
  ## Context
  
  This module implements infrastructure for the following requirements:
  
  - Requirement 1
  - Requirement 2
  
  ## Decision
  
  We've chosen to implement the following resources:
  
  {{ range .Resources }}
  - {{ .Type }}: {{ .Name }}
  {{ end }}
  
  ## Consequences
  
  - Benefit 1
  - Benefit 2
  - Trade-off 1

output:
  file: "ADR.md"
  mode: replace
EOF

# Generate ADR documentation
thothctl document iac -f terraform --config-file adr-docs.yml
```
