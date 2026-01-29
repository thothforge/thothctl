# Advanced Dependency Visualization with Input Variables

## Feature: Show Explicit Input Variables in Dependency Graph

### Overview
The `--show-inputs` flag enables advanced dependency visualization that shows explicit input variables passed between Terragrunt stacks, not just module dependencies.

### Usage

#### Basic Dependency Graph (Default)
```bash
# Shows module-level dependencies only
thothctl check iac -type deps
```

**Output**: Standard dependency graph showing which modules depend on each other.

#### Advanced Graph with Input Variables
```bash
# Shows explicit input variables from other stacks
thothctl check iac -type deps --show-inputs
```

**Output**: Enhanced dependency graph including:
- Module dependencies
- External dependencies (outside current directory)
- Input variable references between stacks

### How It Works

#### Default Mode
Uses `terragrunt dag graph` command:
```bash
terragrunt dag graph
```

This is an alias for:
```bash
terragrunt list --format=dot --dependencies --external
```

#### Advanced Mode (--show-inputs)
Uses explicit `terragrunt list` command with full flags:
```bash
terragrunt list --format=dot --dependencies --external
```

**Key Differences**:
- `--dependencies`: Includes dependency information in output
- `--external`: Discovers external dependencies (input variables from other stacks)
- `--format=dot`: Outputs in GraphViz DOT format for visualization

### Examples

#### Example 1: Basic Dependencies
```bash
thothctl check iac -type deps
```

**Shows**:
```
vpc
  └─ security-groups
      └─ ec2-instances
```

#### Example 2: With Input Variables
```bash
thothctl check iac -type deps --show-inputs
```

**Shows**:
```
vpc (outputs: vpc_id, subnet_ids)
  └─ security-groups (inputs: vpc_id from vpc)
      └─ ec2-instances (inputs: vpc_id from vpc, sg_id from security-groups)
  └─ rds (inputs: subnet_ids from vpc)
```

### Use Cases

#### 1. Understanding Cross-Stack Dependencies
```bash
# See which stacks consume outputs from other stacks
thothctl check iac -type deps --show-inputs
```

**Useful for**:
- Identifying blast radius of changes
- Understanding data flow between stacks
- Planning refactoring efforts

#### 2. Debugging Dependency Issues
```bash
# When a stack fails due to missing inputs
thothctl check iac -type deps --show-inputs
```

**Helps identify**:
- Missing output values
- Circular dependencies
- Incorrect dependency declarations

#### 3. Documentation Generation
```bash
# Generate comprehensive dependency documentation
thothctl check iac -type deps --show-inputs > dependencies.dot
dot -Tpng dependencies.dot > dependencies.png
```

### Technical Details

#### Terragrunt Commands Used

**Default** (`--show-inputs` not set):
```bash
terragrunt dag graph --working-dir <directory>
```

**Advanced** (`--show-inputs` set):
```bash
terragrunt list --format=dot --dependencies --external --working-dir <directory>
```

#### What Gets Discovered

With `--show-inputs`, Terragrunt discovers:

1. **Direct Dependencies**: Modules explicitly declared in `dependency` blocks
2. **External Dependencies**: Dependencies outside the current working directory
3. **Input Variables**: Variables passed via `dependency` outputs
4. **Transitive Dependencies**: Dependencies of dependencies

### Output Format

Both modes output GraphViz DOT format, which can be:

1. **Displayed in terminal** (ASCII tree visualization)
2. **Converted to images**:
   ```bash
   thothctl check iac -type deps --show-inputs > graph.dot
   dot -Tpng graph.dot > graph.png
   dot -Tsvg graph.dot > graph.svg
   ```

### Configuration

#### Terragrunt Configuration Example

```hcl
# Stack A: VPC
# stacks/vpc/terragrunt.hcl
terraform {
  source = "../../modules/vpc"
}

inputs = {
  cidr_block = "10.0.0.0/16"
}
```

```hcl
# Stack B: Security Groups (depends on VPC)
# stacks/security-groups/terragrunt.hcl
dependency "vpc" {
  config_path = "../vpc"
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id  # ← This is shown with --show-inputs
}
```

### Comparison

| Feature | Default | --show-inputs |
|---------|---------|---------------|
| **Command** | `dag graph` | `list --format=dot --dependencies --external` |
| **Shows modules** | ✅ Yes | ✅ Yes |
| **Shows dependencies** | ✅ Yes | ✅ Yes |
| **Shows external deps** | ✅ Yes | ✅ Yes |
| **Shows input variables** | ❌ No | ✅ Yes |
| **Shows output values** | ❌ No | ✅ Yes |
| **Performance** | Fast | Slightly slower (more discovery) |

### Best Practices

1. **Use default mode for quick checks**:
   ```bash
   thothctl check iac -type deps
   ```

2. **Use --show-inputs for detailed analysis**:
   ```bash
   thothctl check iac -type deps --show-inputs
   ```

3. **Combine with recursive flag**:
   ```bash
   thothctl check iac -type deps --show-inputs --recursive
   ```

4. **Generate documentation**:
   ```bash
   thothctl check iac -type deps --show-inputs > docs/dependencies.dot
   ```

### Troubleshooting

#### Issue: No external dependencies shown
**Solution**: Ensure your Terragrunt configurations use `dependency` blocks:
```hcl
dependency "vpc" {
  config_path = "../vpc"
}
```

#### Issue: Graph is too complex
**Solution**: Use filtering or focus on specific stacks:
```bash
cd stacks/specific-stack
thothctl check iac -type deps --show-inputs
```

#### Issue: Command is slow
**Solution**: The `--show-inputs` flag requires more discovery. For quick checks, use default mode:
```bash
thothctl check iac -type deps  # Faster
```

### Related Commands

- `thothctl check iac -type blast-radius` - Assess change impact
- `thothctl check iac -type tfplan` - Analyze Terraform plans
- `thothctl inventory iac` - Create infrastructure inventory

### References

- [Terragrunt list command documentation](https://terragrunt.gruntwork.io/docs/reference/cli/commands/list/)
- [Terragrunt dag graph documentation](https://terragrunt.gruntwork.io/docs/reference/cli/commands/dag/graph/)
- [GraphViz DOT language](https://graphviz.org/doc/info/lang.html)
