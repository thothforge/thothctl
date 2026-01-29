"""Test mermaid diagram edge labels with mock_outputs."""
import pytest
from pathlib import Path
import tempfile
import shutil
from thothctl.services.document.iac_grunt_graph import DependencyGraphGenerator
from thothctl.core.logger import get_logger


class MockExecutor:
    """Mock executor for testing."""
    def execute(self, command, directory):
        return "", "", 0


@pytest.fixture
def test_stack():
    """Create a test terragrunt stack structure."""
    temp_dir = tempfile.mkdtemp()
    stack_dir = Path(temp_dir) / "test-stack"
    stack_dir.mkdir()
    
    # Create vpc module (no dependencies)
    vpc_dir = stack_dir / "vpc"
    vpc_dir.mkdir()
    (vpc_dir / "terragrunt.hcl").write_text("""
terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v5.0.0"
}

inputs = {
  name = "test-vpc"
  cidr = "10.0.0.0/16"
}
""")
    
    # Create security-groups module (depends on vpc)
    sg_dir = stack_dir / "security-groups"
    sg_dir.mkdir()
    (sg_dir / "terragrunt.hcl").write_text("""
terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-security-group.git?ref=v5.0.0"
}

dependency "vpc" {
  config_path = "../vpc"
  
  mock_outputs = {
    vpc_id = "vpc-mock-12345"
    subnet_ids = ["subnet-1", "subnet-2"]
  }
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id
  name = "test-sg"
}
""")
    
    # Create ec2 module (depends on vpc and security-groups)
    ec2_dir = stack_dir / "ec2"
    ec2_dir.mkdir()
    (ec2_dir / "terragrunt.hcl").write_text("""
terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-ec2-instance.git?ref=v5.0.0"
}

dependency "vpc" {
  config_path = "../vpc"
  
  mock_outputs = {
    vpc_id = "vpc-mock-12345"
  }
}

dependency "sg" {
  config_path = "../security-groups"
  
  mock_outputs = {
    security_group_id = "sg-mock-67890"
  }
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id
  vpc_security_group_ids = [dependency.sg.outputs.security_group_id]
}
""")
    
    yield stack_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


def test_parse_terragrunt_dependencies(test_stack):
    """Test parsing terragrunt.hcl files for dependencies."""
    logger = get_logger("test")
    executor = MockExecutor()
    generator = DependencyGraphGenerator(executor=executor, logger=logger)
    
    # Parse security-groups terragrunt.hcl
    sg_hcl = test_stack / "security-groups" / "terragrunt.hcl"
    deps = generator._parse_terragrunt_hcl(sg_hcl)
    
    assert "vpc" in deps
    assert deps["vpc"]["config_path"] == "../vpc"
    assert "vpc_id" in deps["vpc"]["mock_outputs"]
    assert "subnet_ids" in deps["vpc"]["mock_outputs"]
    
    # Parse ec2 terragrunt.hcl
    ec2_hcl = test_stack / "ec2" / "terragrunt.hcl"
    deps = generator._parse_terragrunt_hcl(ec2_hcl)
    
    assert "vpc" in deps
    assert "sg" in deps
    assert "vpc_id" in deps["vpc"]["mock_outputs"]
    assert "security_group_id" in deps["sg"]["mock_outputs"]


def test_create_mermaid_with_edge_labels(test_stack):
    """Test mermaid diagram creation with edge labels."""
    logger = get_logger("test")
    executor = MockExecutor()
    generator = DependencyGraphGenerator(executor=executor, logger=logger)
    
    # Mock nodes and edges (simulating DOT graph output)
    nodes = ["vpc", "security-groups", "ec2"]
    edges = [
        ("security-groups", "vpc"),  # security-groups depends on vpc
        ("ec2", "vpc"),              # ec2 depends on vpc
        ("ec2", "security-groups")   # ec2 depends on security-groups
    ]
    
    # Build dep_info
    dep_info = {}
    for node in nodes:
        node_path = test_stack / node / "terragrunt.hcl"
        if node_path.exists():
            deps = generator._parse_terragrunt_hcl(node_path)
            if deps:
                dep_info[node] = deps
    
    # Generate mermaid content
    mermaid_content = generator._create_mermaid_content(nodes, edges, dep_info)
    
    print("\n=== Generated Mermaid Content ===")
    print(mermaid_content)
    print("=================================\n")
    
    # Verify structure
    assert "graph LR" in mermaid_content
    assert "%%{init:" in mermaid_content
    
    # Verify nodes
    assert "vpc" in mermaid_content
    assert "security_groups" in mermaid_content  # Note: hyphens replaced with underscores
    assert "ec2" in mermaid_content
    
    # Verify node styling
    assert ":::rootNode" in mermaid_content  # vpc has no dependencies
    assert ":::normalNode" in mermaid_content  # security-groups has 1 dependency
    
    # Verify edge labels with mock_outputs keys
    assert "vpc_id" in mermaid_content
    assert "subnet_ids" in mermaid_content or "vpc_id, subnet_ids" in mermaid_content
    assert "security_group_id" in mermaid_content
    
    # Verify edges exist
    assert "-->" in mermaid_content
    
    # Verify styling classes
    assert "classDef rootNode" in mermaid_content
    assert "classDef normalNode" in mermaid_content
    assert "classDef complexNode" in mermaid_content


def test_edge_label_matching():
    """Test edge label matching logic."""
    logger = get_logger("test")
    executor = MockExecutor()
    generator = DependencyGraphGenerator(executor=executor, logger=logger)
    
    # Test data
    dep_info = {
        "security-groups": {
            "vpc": {
                "config_path": "../vpc",
                "mock_outputs": {
                    "vpc_id": "vpc-123",
                    "subnet_ids": ["subnet-1"]
                }
            }
        },
        "ec2": {
            "vpc": {
                "config_path": "../vpc",
                "mock_outputs": {
                    "vpc_id": "vpc-123"
                }
            },
            "sg": {
                "config_path": "../security-groups",
                "mock_outputs": {
                    "security_group_id": "sg-123"
                }
            }
        }
    }
    
    nodes = ["vpc", "security-groups", "ec2"]
    edges = [
        ("security-groups", "vpc"),  # security-groups depends on vpc
        ("ec2", "vpc"),              # ec2 depends on vpc
        ("ec2", "security-groups")   # ec2 depends on security-groups
    ]
    
    mermaid_content = generator._create_mermaid_content(nodes, edges, dep_info)
    
    print("\n=== Edge Label Test ===")
    print(mermaid_content)
    print("=======================\n")
    
    # Check that edge labels contain the mock_outputs keys
    lines = mermaid_content.split('\n')
    edge_lines = [line for line in lines if '-->' in line]
    
    print("Edge lines found:")
    for line in edge_lines:
        print(f"  {line}")
    
    # Verify at least one edge has a label with mock_outputs keys
    has_labeled_edge = any('|' in line and ('vpc_id' in line or 'security_group_id' in line) 
                          for line in edge_lines)
    
    assert has_labeled_edge, "No edge labels with mock_outputs keys found"


def test_node_classification():
    """Test node classification by dependency count."""
    logger = get_logger("test")
    executor = MockExecutor()
    generator = DependencyGraphGenerator(executor=executor, logger=logger)
    
    dep_info = {
        "node1": {},  # No dependencies - should be rootNode
        "node2": {
            "dep1": {"config_path": "../dep1", "mock_outputs": {"key1": "val1"}}
        },  # 1 dependency - should be normalNode
        "node3": {
            "dep1": {"config_path": "../dep1", "mock_outputs": {}},
            "dep2": {"config_path": "../dep2", "mock_outputs": {}},
            "dep3": {"config_path": "../dep3", "mock_outputs": {}}
        }  # 3 dependencies - should be complexNode
    }
    
    nodes = ["node1", "node2", "node3"]
    edges = []
    
    mermaid_content = generator._create_mermaid_content(nodes, edges, dep_info)
    
    print("\n=== Node Classification Test ===")
    print(mermaid_content)
    print("================================\n")
    
    # Verify classification
    assert "node1" in mermaid_content and ":::rootNode" in mermaid_content
    assert "node2" in mermaid_content and ":::normalNode" in mermaid_content
    assert "node3" in mermaid_content and ":::complexNode" in mermaid_content


if __name__ == "__main__":
    # Run tests manually for debugging
    import sys
    
    print("Creating test stack...")
    temp_dir = tempfile.mkdtemp()
    stack_dir = Path(temp_dir) / "test-stack"
    stack_dir.mkdir()
    
    # Create vpc
    vpc_dir = stack_dir / "vpc"
    vpc_dir.mkdir()
    (vpc_dir / "terragrunt.hcl").write_text("""
terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v5.0.0"
}

inputs = {
  name = "test-vpc"
  cidr = "10.0.0.0/16"
}
""")
    
    # Create security-groups
    sg_dir = stack_dir / "security-groups"
    sg_dir.mkdir()
    (sg_dir / "terragrunt.hcl").write_text("""
terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-security-group.git?ref=v5.0.0"
}

dependency "vpc" {
  config_path = "../vpc"
  
  mock_outputs = {
    vpc_id = "vpc-mock-12345"
    subnet_ids = ["subnet-1", "subnet-2"]
  }
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id
  name = "test-sg"
}
""")
    
    print(f"Test stack created at: {stack_dir}")
    print("\nRunning tests...\n")
    
    try:
        # Test 1: Parse dependencies
        print("TEST 1: Parse Terragrunt Dependencies")
        print("-" * 50)
        logger = get_logger("test")
        executor = MockExecutor()
        generator = DependencyGraphGenerator(executor=executor, logger=logger)
        
        sg_hcl = stack_dir / "security-groups" / "terragrunt.hcl"
        deps = generator._parse_terragrunt_hcl(sg_hcl)
        print(f"Parsed dependencies: {deps}")
        assert "vpc" in deps
        print("✅ PASSED\n")
        
        # Test 2: Create mermaid with edge labels
        print("TEST 2: Create Mermaid with Edge Labels")
        print("-" * 50)
        nodes = ["vpc", "security-groups"]
        edges = [("security-groups", "vpc")]  # security-groups depends on vpc
        dep_info = {"security-groups": deps}
        
        mermaid_content = generator._create_mermaid_content(nodes, edges, dep_info)
        print(mermaid_content)
        
        # Check for edge labels
        if "vpc_id" in mermaid_content:
            print("\n✅ PASSED - Edge labels found!")
        else:
            print("\n❌ FAILED - No edge labels found")
            sys.exit(1)
        
    finally:
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up: {temp_dir}")
