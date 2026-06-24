"""Tests for the stack optimizer service."""
import tempfile
from pathlib import Path

import pytest

from thothctl.services.check.stack_optimizer import StackOptimizer


@pytest.fixture
def project_dir():
    """Create a temporary project structure mimicking a terragrunt project."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        resources = base / "resources"

        # Network stacks
        _create_unit(resources / "Network/VPC", deps=[])
        _create_unit(resources / "Network/SecurityGroups/EC2_Bastion", deps=["Network/VPC"])
        _create_unit(resources / "Network/SecurityGroups/RDS_Main", deps=["Network/VPC"])
        _create_unit(resources / "Network/Transit_Gw_Peer", deps=["Network/VPC"])
        _create_unit(resources / "Network/Route53_Hosted_Zone", deps=[])

        # Compute stacks
        _create_unit(resources / "Compute/EC2/EC2_Bastion_Private", deps=[
            "Network/VPC", "Network/SecurityGroups/EC2_Bastion"
        ])

        # Database stacks
        _create_unit(resources / "Database/RDS", deps=[
            "Network/VPC", "Network/SecurityGroups/RDS_Main"
        ])
        _create_unit(resources / "Database/OpenSearch", deps=[
            "Network/VPC", "Network/SecurityGroups/Search_sg"
        ])

        # Security
        _create_unit(resources / "Network/SecurityGroups/Search_sg", deps=["Network/VPC"])

        yield base


def _create_unit(unit_path: Path, deps: list):
    """Create a terragrunt unit with dependencies."""
    unit_path.mkdir(parents=True, exist_ok=True)
    hcl_content = 'include "root" {\n  path = find_in_parent_folders("root.hcl")\n}\n\n'
    for dep in deps:
        dep_name = dep.replace("/", "_").lower()
        hcl_content += f'dependency "{dep_name}" {{\n'
        hcl_content += f'  config_path = "${{get_parent_terragrunt_dir("root")}}/resources/{dep}"\n'
        hcl_content += "}\n\n"
    (unit_path / "terragrunt.hcl").write_text(hcl_content)


class TestStackOptimizer:
    """Test stack optimizer DAG resolution and deduplication."""

    def test_no_overlap_keeps_all(self, project_dir):
        """Stacks with no overlap are all kept."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Network/Route53_Hosted_Zone", "Database/RDS"])

        assert set(result["optimized_filters"]) == {"Network/Route53_Hosted_Zone", "Database/RDS"}
        assert result["removed_redundant"] == []

    def test_subset_is_removed(self, project_dir):
        """Network/VPC is a dep of Compute/EC2/EC2_Bastion_Private, but
        Network/** includes Transit_Gw and Route53 which are NOT deps of Compute.
        So Network/** should be KEPT (not a strict subset)."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Network/**", "Compute/EC2/EC2_Bastion_Private"])

        # Network/** resolves to 5 units (VPC, 2 SGs, Transit, Route53 + Search_sg)
        # Compute/EC2/EC2_Bastion_Private with deps = {EC2_Bastion_Private, VPC, EC2_Bastion SG}
        # Network/** is NOT a subset of Compute's deps, so BOTH are kept
        assert "Network/**" in result["optimized_filters"]
        assert "Compute/EC2/EC2_Bastion_Private" in result["optimized_filters"]

    def test_strict_subset_removed(self, project_dir):
        """A single unit that's a dep of another stack's full set is removed."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Network/VPC", "Compute/EC2/EC2_Bastion_Private"])

        # Network/VPC resolves to just {VPC} (no deps itself)
        # Compute/EC2/EC2_Bastion_Private with deps = {EC2_Bastion_Private, VPC, EC2_Bastion SG}
        # {VPC} ⊂ {EC2_Bastion_Private, VPC, EC2_Bastion SG} → VPC is redundant
        assert result["optimized_filters"] == ["Compute/EC2/EC2_Bastion_Private"]
        assert result["removed_redundant"] == ["Network/VPC"]

    def test_user_explicit_broad_stack_kept(self, project_dir):
        """Network/** is broader than what Compute needs, so it's kept —
        the user explicitly wants all Network deployed (e.g. Transit GW change)."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Network/**", "Database/RDS"])

        assert "Network/**" in result["optimized_filters"]
        assert "Database/RDS" in result["optimized_filters"]

    def test_identical_stacks_deduped(self, project_dir):
        """Duplicate entries are deduped (one is subset of the other, both equal)."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Database/RDS", "Database/RDS"])

        # Equal sets → neither is a strict subset, both kept (idempotent)
        assert "Database/RDS" in result["optimized_filters"]

    def test_output_details(self, project_dir):
        """Result contains per-stack detail information."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Network/VPC", "Database/RDS"])

        assert "details" in result
        assert "Network/VPC" in result["details"]
        assert "direct_units" in result["details"]["Network/VPC"]
        assert "with_deps" in result["details"]["Network/VPC"]

    def test_empty_stacks(self, project_dir):
        """Empty input returns empty result."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize([])

        assert result["optimized_filters"] == []
        assert result["removed_redundant"] == []

    def test_single_stack(self, project_dir):
        """Single stack is always kept."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize(["Compute/EC2/EC2_Bastion_Private"])

        assert result["optimized_filters"] == ["Compute/EC2/EC2_Bastion_Private"]
        assert result["removed_redundant"] == []

    def test_multiple_compute_stacks_with_network(self, project_dir):
        """Network/** + multiple Compute stacks: all kept because Network has units
        not covered by Compute deps (Transit GW, Route53), and Compute stacks
        have their own direct units not in Network."""
        optimizer = StackOptimizer(base_path=project_dir, stacks_base="resources")
        result = optimizer.optimize([
            "Network/**",
            "Compute/EC2/EC2_Bastion_Private",
            "Database/RDS",
        ])

        # All 3 are kept: Network has Transit/Route53 not in others,
        # Compute has its own unit, Database has its own unit
        assert len(result["optimized_filters"]) == 3
        assert "Network/**" in result["optimized_filters"]
        assert "Compute/EC2/EC2_Bastion_Private" in result["optimized_filters"]
        assert "Database/RDS" in result["optimized_filters"]
        assert result["removed_redundant"] == []
