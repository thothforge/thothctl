# ThothCTL Use Cases

This directory contains documentation for various use cases of the ThothCTL framework. Each document provides detailed information about a specific functionality, including command options, examples, and best practices.

## Available Use Cases

### [Generate Components](generate_components.md)
Create infrastructure components according to project rules and conventions.

### [Generate Stacks](generate_stacks.md)
Generate infrastructure stacks based on configuration files or command-line parameters.

### [Space Management](space_management.md)
Organize projects within logical spaces with consistent configurations.

## Common Patterns

ThothCTL commands follow these common patterns:

1. **Initialization Commands**: `thothctl init <resource>`
   - Create and set up new resources
   - Example: `thothctl init project`, `thothctl init space`

2. **Generation Commands**: `thothctl generate <resource>`
   - Generate code or configurations based on templates or rules
   - Example: `thothctl generate component`, `thothctl generate stacks`

3. **List Commands**: `thothctl list <resource>`
   - Display resources managed by ThothCTL
   - Example: `thothctl list projects`, `thothctl list spaces`

4. **Remove Commands**: `thothctl remove <resource>`
   - Remove resources managed by ThothCTL
   - Example: `thothctl remove project`, `thothctl remove space`

5. **Check Commands**: `thothctl check <resource>`
   - Validate resources against rules or best practices
   - Example: `thothctl check project`

## Getting Started

If you're new to ThothCTL, we recommend starting with:

1. Initialize a space: `thothctl init space --space-name development`
2. Create a project in that space: `thothctl init project --project-name my_project --space development`
3. Generate components for your project: `thothctl generate component --component-type module --component-name network --component-path ./modules`
4. Generate stacks for your infrastructure: `thothctl generate stacks --create-example` followed by `thothctl generate stacks --config-file stack-config-example.yaml`

## Best Practices

1. **Version Control**: Store your ThothCTL configurations in version control
2. **Consistent Naming**: Use consistent naming conventions for spaces, projects, and components
3. **Documentation**: Document your custom templates and configurations
4. **Automation**: Integrate ThothCTL commands into your CI/CD pipelines
5. **Modular Design**: Create reusable components and templates

## Extending ThothCTL

ThothCTL is designed to be extensible. You can:

1. Create custom templates for components
2. Define project structures in `.thothcf.toml` files
3. Create custom commands by extending the ThothCTL framework
4. Integrate with other tools in your development workflow

For more information on extending ThothCTL, see the [Developer Guide](../developer_guide.md).
