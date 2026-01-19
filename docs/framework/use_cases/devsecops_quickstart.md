# Quick Start: DevSecOps for IaC

## 🚀 5-Minute Quick Start

### For Beginners

#### Step 1: Install ThothCTL
```bash
pip install thothctl
```

#### Step 2: Create Your First Project
```bash
# Initialize a new Terraform project
thothctl init project --name my-first-infra --template terraform-aws
cd my-first-infra
```

#### Step 3: Check Your Environment
```bash
# Verify you have all required tools
thothctl check environment
```

#### Step 4: Run Security Scan
```bash
# Scan your infrastructure code
thothctl scan iac --tool checkov
```

#### Step 5: View Results
```bash
# Launch the dashboard
thothctl dashboard launch
```

**🎉 Congratulations!** You've completed your first DevSecOps workflow!

---

## 🎯 Common Use Cases

### Use Case 1: Security Audit
```bash
# Run all security scanners
thothctl scan iac --tool checkov
thothctl scan iac --tool trivy
thothctl scan iac --tool tfsec

# View consolidated results
thothctl dashboard launch
```

### Use Case 2: Cost Estimation
```bash
# Create Terraform plan
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Analyze costs
thothctl check iac --type cost-analysis --plan-file tfplan.json
```

### Use Case 3: Change Impact Analysis
```bash
# Assess blast radius
thothctl check iac --type blast-radius --plan-file tfplan.json
```

### Use Case 4: Dependency Management
```bash
# Create inventory and check for updates
thothctl inventory iac --check-versions
```

---

## 📚 Learning Path

### Level 1: Beginner (Week 1)
- [ ] Install ThothCTL
- [ ] Initialize first project
- [ ] Run basic security scan
- [ ] Generate documentation

### Level 2: Intermediate (Week 2-3)
- [ ] Set up CI/CD integration
- [ ] Use all security scanners
- [ ] Perform cost analysis
- [ ] Create infrastructure inventory

### Level 3: Advanced (Week 4+)
- [ ] Implement blast radius assessment
- [ ] Set up compliance policies
- [ ] Automate full DevSecOps pipeline
- [ ] Customize templates and workflows

---

## 🔗 Related Resources

- [Complete DevSecOps SDLC Guide](devsecops_sdlc.md)
- [Command Reference](framework/commands/check/check_overview.md)
- [Security Scanning Guide](framework/commands/scan/scan_overview.md)
- [Cost Analysis Guide](framework/commands/check/cost-analysis.md)
