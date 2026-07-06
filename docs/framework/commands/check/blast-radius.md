# Blast Radius Assessment

The blast radius assessment feature provides ITIL v4 compliant risk analysis for infrastructure changes by combining dependency analysis with planned changes to assess the potential impact before deployment.

## Overview

Blast radius assessment helps teams:
- **Minimize Risk**: Identify potential issues before deployment
- **Improve Planning**: Provide clear mitigation and rollback steps
- **Enforce Governance**: ITIL v4 compliant approval workflows
- **Enhance Visibility**: Show complete impact of changes

## Command Usage

### Basic Blast Radius Assessment
```bash
thothctl check -type blast-radius --recursive
```

### With Specific Plan File
```bash
thothctl check -type blast-radius --recursive --plan-file tfplan.json
```

### Command Options
- `--recursive`: Analyze dependencies recursively through subdirectories
- `--plan-file`: Path to terraform plan JSON file (optional)
- `--directory`: Target directory to analyze (default: current directory)

## Risk Assessment Formula

### Base Risk Factors
The assessment uses weighted risk factors to calculate component risk scores:

| Factor | Weight | Description |
|--------|--------|-------------|
| Changes Frequency | 30% | How often the component changes |
| Dependencies Count | 25% | Number of dependencies |
| Complexity | 20% | Complexity of the component |
| Criticality | 15% | How critical the component is |
| Recent Changes | 10% | Recent changes to the component |

### Risk Calculation
```python
component_risk = (
    changes_frequency * 0.3 +
    dependencies_count * 0.25 +
    complexity * 0.2 +
    criticality * 0.15 +
    recent_changes * 0.1
)
```

### Change Type Multipliers
Different change types have varying risk levels:

| Change Type | Risk Multiplier | Description |
|-------------|----------------|-------------|
| Delete | 1.5x | Deletion is 50% more risky |
| Replace | 1.3x | Replacement is 30% more risky |
| Update | 1.0x | Update is baseline risk |
| Create | 0.8x | Creation is 20% less risky |
| No Change | 0.0x | No change = no risk |

### Overall Risk Assessment
```python
# Weighted combination of factors
final_risk_score = (
    avg_risk * 0.6 +          # 60% weight on average risk
    max_risk * 0.3 +          # 30% weight on maximum risk
    blast_radius_factor * 0.1  # 10% weight on blast radius size
)
```

## ITIL v4 Risk Categories

### Risk Levels and Thresholds

| Risk Score | Risk Level | Color | ITIL Change Type | Approval Required |
|------------|------------|-------|------------------|-------------------|
| 0.0 - 0.3  | LOW        | 🟢 Green | STANDARD | Automated |
| 0.3 - 0.6  | MEDIUM     | 🟡 Yellow | NORMAL | Team Lead |
| 0.6 - 0.8  | HIGH       | 🟠 Orange | NORMAL | Senior Management |
| 0.8 - 1.0  | CRITICAL   | 🔴 Red | EMERGENCY | CAB Approval |

### Change Types

#### STANDARD Changes
- **Risk Level**: LOW
- **Approval**: Automated process
- **Timing**: Can be deployed during business hours
- **Monitoring**: Basic monitoring sufficient

#### NORMAL Changes
- **Risk Level**: MEDIUM to HIGH
- **Approval**: Team Lead or Senior Management
- **Timing**: Scheduled maintenance windows recommended
- **Monitoring**: Enhanced monitoring required

#### EMERGENCY Changes
- **Risk Level**: CRITICAL
- **Approval**: Change Advisory Board (CAB)
- **Timing**: Immediate with full incident response
- **Monitoring**: Real-time monitoring with on-call team

## Output Example

### High Risk Scenario
```bash
================================================================================
🎯 BLAST RADIUS ASSESSMENT (ITIL v4 Compliant)
================================================================================

┌─────────────────── 📊 Risk Summary ───────────────────┐
│ Risk Level: HIGH                                      │
│ Change Type: NORMAL                                   │
│ Total Components: 12                                  │
│ Affected Components: 7                                │
└───────────────────────────────────────────────────────┘

                    💥 Affected Components                     
┌─────────────────────┬──────────────┬────────────┬─────────────┐
│ Component           │ Change Type  │ Risk Score │ Criticality │
├─────────────────────┼──────────────┼────────────┼─────────────┤
│ vpc-main            │ update       │ 0.85       │ critical    │
│ security-group-web  │ replace      │ 0.72       │ high        │
│ rds-primary         │ update       │ 0.68       │ high        │
└─────────────────────┴──────────────┴────────────┴─────────────┘

┌─────────────────── 📋 ITIL v4 Recommendations ───────────────────┐
│ • ⚠️ HIGH: Require senior management approval                    │
│ • ⚠️ Schedule during maintenance window                          │
│ • ⚠️ Prepare detailed rollback procedures                       │
│ • ⚠️ Monitor affected systems closely                           │
└──────────────────────────────────────────────────────────────────┘
```

### Low Risk Scenario
```bash
┌─────────────────── 📊 Risk Summary ───────────────────┐
│ Risk Level: LOW                                       │
│ Change Type: STANDARD                                 │
│ Total Components: 8                                   │
│ Affected Components: 2                                │
└───────────────────────────────────────────────────────┘

┌─────────────────── 📋 ITIL v4 Recommendations ───────────────────┐
│ • ✅ LOW: Standard change process applies                        │
│ • ✅ Can be deployed during business hours                       │
│ • ✅ Basic monitoring sufficient                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Integration with Existing Commands

### Dependency Analysis Integration
The blast radius assessment leverages the existing dependency analysis:
```bash
# First run dependency analysis
thothctl check -type deps --recursive

# Then run blast radius assessment
thothctl check -type blast-radius --recursive
```

### Plan Analysis Integration
Works with terraform plan files:
```bash
# Generate plan first
terraform plan -out=tfplan.json

# Assess blast radius with plan
thothctl check -type blast-radius --plan-file tfplan.json --recursive
```

## Best Practices

### Pre-Deployment Workflow
1. **Generate Dependencies**: Run `thothctl check -type deps --recursive`
2. **Create Plan**: Generate terraform plan with `terraform plan -out=tfplan.json`
3. **Assess Risk**: Run `thothctl check -type blast-radius --plan-file tfplan.json --recursive`
4. **Review Results**: Follow ITIL v4 recommendations for approval
5. **Implement Mitigations**: Execute recommended mitigation steps
6. **Deploy with Monitoring**: Deploy with appropriate monitoring level

### Risk Mitigation Strategies

#### For HIGH/CRITICAL Risk Changes
- **Phased Deployment**: Break changes into smaller, less risky phases
- **Blue-Green Deployment**: Use blue-green deployment strategies
- **Canary Releases**: Deploy to subset of infrastructure first
- **Maintenance Windows**: Schedule during low-traffic periods
- **Rollback Testing**: Test rollback procedures before deployment

#### For MEDIUM Risk Changes
- **Staging Validation**: Thorough testing in staging environment
- **Monitoring Setup**: Enhanced monitoring during deployment
- **Team Coordination**: Ensure team availability during deployment

#### For LOW Risk Changes
- **Standard Process**: Follow normal deployment procedures
- **Basic Monitoring**: Standard monitoring sufficient
- **Documentation**: Ensure changes are properly documented

## Troubleshooting

### Common Issues

#### No Dependencies Found
```bash
# Ensure terragrunt.hcl files exist
ls -la */terragrunt.hcl

# Check directory structure
thothctl check -type deps --recursive
```

#### Plan File Not Found
```bash
# Generate plan file first
terraform plan -out=tfplan.json

# Or use without plan file
thothctl check -type blast-radius --recursive
```

#### High Risk False Positives
- Review component criticality settings
- Check dependency graph accuracy
- Validate change type detection
- Consider component-specific risk factors

## Configuration

### Risk Threshold Customization
Risk thresholds can be customized in the service configuration:

```python
risk_thresholds = {
    ChangeRisk.LOW: 0.3,      # Adjust as needed
    ChangeRisk.MEDIUM: 0.6,   # Adjust as needed
    ChangeRisk.HIGH: 0.8,     # Adjust as needed
    ChangeRisk.CRITICAL: 1.0  # Maximum risk
}
```

### Component Criticality Override
Components can be marked with specific criticality levels:
- **Critical**: Core infrastructure components
- **High**: Important but not critical components
- **Medium**: Standard components
- **Low**: Non-essential components

## Related Commands

- [`thothctl check -type deps`](../check/deps.md) - Dependency analysis
- [`thothctl check -type plan`](../check/plan.md) - Plan validation
- [`thothctl inventory iac`](../inventory/iac.md) - Infrastructure inventory
- [`thothctl scan iac`](../scan/iac.md) - Security scanning

## Blast Radius v0.20.0+ Enhancements

Starting with v0.20.0, the blast radius command includes significant improvements to change detection, topology generation, and report outputs.

### Enhanced Usage

```bash
thothctl check iac -type blast-radius --recursive
```

### What it does (v0.20.0+)

1. Finds `tfplan.json` files recursively across all stacks
2. Filters out no-op/read resources (only create/update/delete/replace affect blast radius)
3. Propagates changes through the dependency graph
4. Classifies risk: LOW/MEDIUM/HIGH/CRITICAL using ITIL v4
5. Generates ITIL change type: STANDARD/NORMAL/EMERGENCY
6. Saves reports to `Reports/blast-radius/blast_radius_*.json`
7. Generates infrastructure topology diagram (`Reports/topology/`)

### Report Outputs

```
Reports/
├── blast-radius/
│   └── blast_radius_20260705_*.json    # Risk assessment data
└── topology/
    ├── topology.json                    # Full topology + mermaid
    ├── topology.mmd                     # Standalone mermaid file
    └── architecture.png                 # Professional AWS diagram
```

### No-Changes Handling

When terraform plan shows no changes (all no-op), blast radius returns LOW risk with:

- Zero affected components
- Context about total infrastructure size
- Clear message that no create/update/delete actions were detected

This ensures pipelines don't fail on plans with no actionable changes while still providing visibility into the existing infrastructure footprint.

### Infrastructure Topology

The blast radius command automatically generates visual topology outputs:

- **Mermaid diagram** with color-coded nodes (create=blue, update=orange, delete=red dashed)
- **PNG architecture diagram** with official AWS icons via mingrammer/diagrams
- **Resource-level detail** per stack with category and action badges

The topology files are written to `Reports/topology/` and include both machine-readable JSON and renderable diagram formats suitable for embedding in PRs or documentation.

### Dashboard Integration

The web dashboard shows blast radius + topology in a unified view under the **💥 Blast Radius** tab. This includes:

- Risk summary with ITIL classification
- Interactive topology diagram
- Per-stack affected resource breakdown
- Change action badges (create, update, delete, replace)

## Dual-Mode Cost Analysis (v0.20.0+)

The `thothctl check iac -type cost-analysis` command now provides dual-mode cost estimation:

### Usage

```bash
thothctl check iac -type cost-analysis --recursive
```

### Modes

- **Change delta**: Cost of resources being created/modified (for PR reviews). This shows the incremental cost impact of the proposed changes.
- **Total running cost**: Cost of ALL planned resources (from `planned_values`). This provides a full picture of what the infrastructure costs to run.

### No-Changes Behavior

When no changes are detected in the plan, cost analysis shows the total running cost instead of `$0`. This gives teams continuous visibility into their infrastructure spend even when no modifications are pending.

### JSON Report Fields

The cost analysis JSON report includes:

| Field | Description |
|-------|-------------|
| `total_running_monthly_cost` | Monthly cost of all planned resources |
| `total_running_annual_cost` | Annual projection of all planned resources |
| `total_planned_resources` | Count of all resources in the plan |
| `change_delta_monthly_cost` | Monthly cost delta from changes only |
| `change_delta_annual_cost` | Annual cost delta from changes only |

### Example Output

```json
{
  "total_running_monthly_cost": 1250.00,
  "total_running_annual_cost": 15000.00,
  "total_planned_resources": 47,
  "change_delta_monthly_cost": 85.50,
  "change_delta_annual_cost": 1026.00
}
```

This dual-mode approach ensures that PR reviews show the marginal cost of changes while still providing the full cost picture for governance and budgeting.