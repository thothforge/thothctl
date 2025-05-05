"""Utility for fetching Terraform module details from registry."""
import json
import os
import re
import requests
from typing import Dict, Any, Optional


class TerraformModuleDetails:
    """Class for fetching Terraform module details from registry."""
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize the TerraformModuleDetails class.
        
        Args:
            cache_dir: Directory to cache module details
        """
        if cache_dir is None:
            # Use default cache directory in the same directory as this file
            self.cache_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "..", "..", "services", "generate", "create_stacks", ".registry_cache"
            )
        else:
            self.cache_dir = cache_dir
            
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def get_module_details(
        self, namespace: str, name: str, provider: str = "aws"
    ) -> Optional[Dict[str, Any]]:
        """
        Get module details from registry or cache.
        
        Args:
            namespace: Module namespace
            name: Module name
            provider: Provider name
            
        Returns:
            Dictionary containing module details or None if not found
        """
        # Check if module details are cached
        cache_file = os.path.join(self.cache_dir, f"{namespace}-{name}-{provider}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                # If there's an error reading the cache, continue to fetch from registry
                pass
                
        # Fetch module details from registry
        try:
            # For this implementation, we'll create mock module details
            # In a real implementation, you would fetch from the Terraform registry API
            module_details = self._create_mock_module_details(namespace, name, provider)
            
            # Cache module details
            with open(cache_file, "w") as f:
                json.dump(module_details, f, indent=2)
                
            return module_details
        except Exception as e:
            print(f"Error fetching module details: {e}")
            return None
            
    def _create_mock_module_details(
        self, namespace: str, name: str, provider: str
    ) -> Dict[str, Any]:
        """
        Create mock module details for testing.
        
        Args:
            namespace: Module namespace
            name: Module name
            provider: Provider name
            
        Returns:
            Dictionary containing mock module details
        """
        # Basic module info
        basic_info = {
            "id": f"{namespace}/{name}/{provider}",
            "namespace": namespace,
            "name": name,
            "provider": provider,
            "version": "1.0.0",
            "description": f"Mock {name} module for {provider}",
        }
        
        # Root module inputs and outputs based on module name
        root = {"inputs": [], "outputs": []}
        
        # Add inputs and outputs based on module name
        if name == "vpc":
            root["inputs"] = [
                {
                    "name": "vpc_cidr",
                    "type": "string",
                    "description": "The CIDR block for the VPC",
                    "default": "10.0.0.0/16",
                },
                {
                    "name": "azs",
                    "type": "list(string)",
                    "description": "A list of availability zones in the region",
                },
                {
                    "name": "private_subnets",
                    "type": "list(string)",
                    "description": "A list of private subnet CIDR blocks",
                },
                {
                    "name": "public_subnets",
                    "type": "list(string)",
                    "description": "A list of public subnet CIDR blocks",
                },
                {
                    "name": "database_subnets",
                    "type": "list(string)",
                    "description": "A list of database subnet CIDR blocks",
                    "default": [],
                },
            ]
            root["outputs"] = [
                {
                    "name": "vpc_id",
                    "description": "The ID of the VPC",
                    "value": "module.vpc.vpc_id",
                },
                {
                    "name": "private_subnets",
                    "description": "List of IDs of private subnets",
                    "value": "module.vpc.private_subnets",
                },
                {
                    "name": "public_subnets",
                    "description": "List of IDs of public subnets",
                    "value": "module.vpc.public_subnets",
                },
                {
                    "name": "database_subnets",
                    "description": "List of IDs of database subnets",
                    "value": "module.vpc.database_subnets",
                },
            ]
        elif name == "rds":
            root["inputs"] = [
                {
                    "name": "identifier",
                    "type": "string",
                    "description": "The name of the RDS instance",
                },
                {
                    "name": "engine",
                    "type": "string",
                    "description": "The database engine to use",
                },
                {
                    "name": "engine_version",
                    "type": "string",
                    "description": "The engine version to use",
                },
                {
                    "name": "instance_class",
                    "type": "string",
                    "description": "The instance type of the RDS instance",
                },
                {
                    "name": "allocated_storage",
                    "type": "number",
                    "description": "The allocated storage in gigabytes",
                    "default": 20,
                },
                {
                    "name": "db_subnet_group_name",
                    "type": "string",
                    "description": "Name of DB subnet group",
                },
                {
                    "name": "vpc_security_group_ids",
                    "type": "list(string)",
                    "description": "List of VPC security groups to associate",
                },
            ]
            root["outputs"] = [
                {
                    "name": "db_instance_address",
                    "description": "The address of the RDS instance",
                    "value": "module.db.this_db_instance_address",
                },
                {
                    "name": "db_instance_id",
                    "description": "The RDS instance ID",
                    "value": "module.db.this_db_instance_id",
                },
                {
                    "name": "db_instance_endpoint",
                    "description": "The connection endpoint",
                    "value": "module.db.this_db_instance_endpoint",
                },
            ]
        elif name == "ec2-instance":
            root["inputs"] = [
                {
                    "name": "name",
                    "type": "string",
                    "description": "Name to be used on EC2 instance created",
                },
                {
                    "name": "ami",
                    "type": "string",
                    "description": "ID of AMI to use for the instance",
                },
                {
                    "name": "instance_type",
                    "type": "string",
                    "description": "The type of instance to start",
                    "default": "t3.micro",
                },
                {
                    "name": "subnet_id",
                    "type": "string",
                    "description": "The VPC Subnet ID to launch in",
                },
                {
                    "name": "vpc_security_group_ids",
                    "type": "list(string)",
                    "description": "A list of security group IDs to associate with",
                    "default": [],
                },
            ]
            root["outputs"] = [
                {
                    "name": "id",
                    "description": "The ID of the instance",
                    "value": "module.ec2_instance.id",
                },
                {
                    "name": "arn",
                    "description": "The ARN of the instance",
                    "value": "module.ec2_instance.arn",
                },
                {
                    "name": "private_ip",
                    "description": "The private IP address assigned to the instance",
                    "value": "module.ec2_instance.private_ip",
                },
            ]
        
        # Return complete module details
        return {
            "basic_info": basic_info,
            "root": root,
        }
