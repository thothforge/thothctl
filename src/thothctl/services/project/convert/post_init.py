"""Post-initialization script for ThothCTL."""
import os
import logging
from pathlib import Path
from colorama import Fore
import toml

def add_project_properties_to_thothcf(project_dir, project_properties):
    """
    Add project_properties to .thothcf.toml
    
    :param project_dir: Project directory
    :param project_properties: Project properties
    """
    thothcf_file = os.path.join(project_dir, '.thothcf.toml')
    
    if not os.path.exists(thothcf_file):
        logging.error(f"{Fore.RED}Error: {thothcf_file} does not exist{Fore.RESET}")
        return
    
    # Read the existing content
    try:
        with open(thothcf_file, 'r') as f:
            content = f.read()
    except Exception as e:
        logging.error(f"{Fore.RED}Error reading {thothcf_file}: {str(e)}{Fore.RESET}")
        return
    
    # Check if project_properties already exists
    if "[project_properties]" in content:
        logging.info(f"{Fore.GREEN}project_properties already exists in {thothcf_file}{Fore.RESET}")
        return
    
    # Create the project_properties section
    project_name = Path(project_dir).name
    if not project_properties:
        project_properties = {
            'project': project_name,
            'environment': 'dev',
            'owner': 'thothctl',
            'client': 'thothctl',
            'backend_region': 'us-east-2',
            'dynamodb_backend': 'db-terraform-lock',
            'backend_bucket': f"{project_name}-tfstate",
            'region': 'us-east-2'
        }
    
    # Format the project_properties section
    project_properties_section = """
# Project Properties
[project_properties]
"""
    for key, value in project_properties.items():
        project_properties_section += f'{key} = "{value}"\n'
    
    project_properties_section += "\n"
    
    # Write the updated content
    try:
        with open(thothcf_file, 'w') as f:
            f.write(project_properties_section)
            f.write(content)
        
        logging.info(f"{Fore.GREEN}Successfully added project_properties to {thothcf_file}{Fore.RESET}")
    except Exception as e:
        logging.error(f"{Fore.RED}Error writing to {thothcf_file}: {str(e)}{Fore.RESET}")
