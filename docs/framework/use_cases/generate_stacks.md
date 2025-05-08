# ThothCTL Generate Stacks

## Overview

The `thothctl generate stacks` command allows you to generate infrastructure stacks based on a YAML configuration file or command-line parameters. This command helps you create consistent, well-structured infrastructure code by automating the creation of Terragrunt configurations for multiple modules within a stack.

## Use Cases

- **Infrastructure as Code (IaC) Scaffolding**: Quickly generate the structure for new infrastructure stacks
- **Standardized Deployments**: Ensure consistent configuration across environments
- **Module Dependency Management**: Automatically handle dependencies between infrastructure modules
- **Configuration Reuse**: Define infrastructure once in YAML and deploy to multiple environments

## Command Options

```
Usage: thothctl generate stacks [OPTIONS]

  Generate infrastructure stacks based on configuration

Options:
  --create-example            Create an example stack configuration file
  -o, --output-dir DIRECTORY  Directory where stacks will be generated
  -m, --modules TEXT          Comma-separated list of modules to include in
                              the stack
  -s, --stack-name TEXT       Name of the stack to generate (when not using
                              config file)
  -c, --config-file FILE      Path to YAML configuration file defining stacks
                              and modules
  --help                      Show this message and exit.
```

## Basic Usage

### Creating an Example Configuration

To get started, you can generate an example configuration file:

```bash
thothctl generate stacks --create-example
```

This will create a `stack-config-example.yaml` file in your current directory with a sample configuration.

### Generating Stacks from Configuration File

Once you have a configuration file, you can generate stacks:

```bash
thothctl generate stacks --config-file stack-config-example.yaml --output-dir ./infrastructure
```

This will create the stack structure in the specified output directory.

### Creating a Single Stack

You can also create a single stack with specified modules:

```bash
thothctl generate stacks --stack-name production --modules vpc,rds,ec2-instance
```

## Configuration File Format

The configuration file uses YAML format and has the following structure:

```yaml
cloud: aws  # Cloud provider

modules:
  - name: vpc  # Module name
    variables:  # Module variables
      vpc_cidr: "10.0.0.0/16"
      environment: "production"
  
  - name: ec2-instance
    variables:
      subnet_id: vpc.private_subnets  # Reference to another module's output
    dependencies:  # Module dependencies
      - vpc
  
  - name: rds
    dependencies:
      - vpc
    variables:
      engine: "postgres"
      engine_version: "15.1"
      instance_class: "db.t3.medium"
      database_subnets: vpc.database_subnets

stacks:
  - name: production-platform  # Stack name
    modules:  # Modules to include in this stack
      - vpc
      - rds
      - ec2-instance
```

### Configuration Elements

- **cloud**: The cloud provider (e.g., aws, azure)
- **modules**: List of infrastructure modules
  - **name**: Module name (corresponds to Terraform module)
  - **variables**: Key-value pairs of module inputs
  - **dependencies**: List of modules this module depends on
- **stacks**: List of stacks to generate
  - **name**: Stack name
  - **modules**: List of modules to include in the stack

## Generated Structure

For a configuration with a stack named `production-platform` containing modules `vpc`, `rds`, and `ec2-instance`, the command will generate:

```
infrastructure/
└── production-platform/
    ├── provider.hcl
    ├── root.hcl
    ├── vpc/
    │   └── terragrunt.hcl
    ├── rds/
    │   └── terragrunt.hcl
    └── ec2-instance/
        └── terragrunt.hcl
```

Each `terragrunt.hcl` file will include:
- Include blocks for root and provider configurations
- Dependency blocks for module dependencies
- Input variables with appropriate references to dependent modules

## Advanced Features

### Variable References

You can reference outputs from other modules in your variables:

```yaml
variables:
  subnet_id: vpc.private_subnets
```

This will be translated to:

```hcl
inputs = {
  subnet_id = dependency.vpc.outputs.private_subnets
}
```

### Dependency Management

The command automatically:
- Creates dependency blocks for explicit dependencies
- Infers dependencies from variable references
- Generates appropriate mock outputs for testing

## Examples

### Basic VPC and EC2 Stack

```yaml
cloud: aws

modules:
  - name: vpc
    variables:
      vpc_cidr: "10.0.0.0/16"
      azs: ["us-east-1a", "us-east-1b"]
      private_subnets: ["10.0.1.0/24", "10.0.2.0/24"]
      public_subnets: ["10.0.101.0/24", "10.0.102.0/24"]
  
  - name: ec2-instance
    dependencies:
      - vpc
    variables:
      instance_type: "t3.micro"
      subnet_id: vpc.private_subnets[0]

stacks:
  - name: dev-environment
    modules:
      - vpc
      - ec2-instance
```

### Multi-Environment Stack

```yaml
cloud: aws

modules:
  - name: vpc
    variables:
      vpc_cidr: "10.0.0.0/16"
  
  - name: rds
    dependencies:
      - vpc
    variables:
      engine: "postgres"
      engine_version: "15.1"

stacks:
  - name: production
    modules:
      - vpc
      - rds
  
  - name: staging
    modules:
      - vpc
      - rds
```

## Best Practices

1. **Organize by Environment**: Create separate stacks for different environments (dev, staging, production)
2. **Explicit Dependencies**: Always declare module dependencies explicitly
3. **Use Variable References**: Reference outputs from other modules instead of hardcoding values
4. **Version Control**: Store your stack configuration files in version control
5. **Consistent Naming**: Use consistent naming conventions for modules and stacks

## Troubleshooting

### Common Issues

- **Module Not Found**: Ensure the module name in your configuration matches a valid Terraform module
- **Invalid References**: Check that variable references point to valid outputs from dependency modules
- **Permission Issues**: Ensure you have write permissions to the output directory
- **YAML Syntax**: Verify your YAML configuration has proper indentation and structure

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug generate stacks --config-file stack-config.yaml
```
