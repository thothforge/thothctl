# Quick Start: DevSecOps for IaC

## 🚀 5-Minute Quick Start

### For Beginners

#### Step 1: Install ThothCTL
```bash
pip install thothctl
```

#### Step 2: Guided Onboarding
```bash
thothctl quickstart
```

The `quickstart` command interactively walks you through environment detection, space creation, project initialization, and your first security scan — all in one guided flow.

#### Step 3: View Results
```bash
# Launch the dashboard
thothctl dashboard launch
```

**🎉 Congratulations!** You've completed your first DevSecOps workflow!

> **Already have a project?** You can skip `quickstart` and jump straight to scanning:
> ```bash
> cd my-existing-infra
> thothctl scan iac -t checkov
> ```

---

## 🎯 Common Use Cases

### Use Case 1: Security Audit
```bash
# Run multiple security scanners
thothctl scan iac -t checkov -t trivy

# View consolidated results
thothctl dashboard launch
```

### Use Case 2: Cost Estimation
```bash
# Create Terraform plan
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Analyze costs
thothctl check iac -type cost-analysis --plan-file tfplan.json
```

### Use Case 3: Change Impact Analysis
```bash
# Assess blast radius
thothctl check iac -type blast-radius --plan-file tfplan.json
```

### Use Case 4: Dependency Management
```bash
# Create inventory and check for updates
thothctl inventory iac --check-versions
```

---

---

## ⚡ One-Command Pipeline

Once you're familiar with the basics, use the workflow command to run entire SDLC phases:

```bash
# Quick security audit
thothctl workflow devsecops --phase secure

# Full DevSecOps pipeline
thothctl workflow devsecops --phase all

# Pre-deployment gate (blocks on violations)
thothctl workflow devsecops --phase pre-deploy --enforcement hard
```

For the complete phase reference, see the [Workflow Command Documentation](../commands/workflow/workflow_devsecops.md).

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
- [Command Reference](../commands/check/check_overview.md)
- [Security Scanning Guide](../commands/scan/scan_overview.md)
- [Cost Analysis Guide](../commands/check/cost-analysis.md)
