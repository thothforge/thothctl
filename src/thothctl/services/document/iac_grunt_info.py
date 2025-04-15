import os
from pathlib import Path
import hcl2
import re
from typing import Optional, Dict, Any


class TerragruntInfoGenerator:
    def __init__(self, logger):
        self.logger = logger

    def _parse_terragrunt_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse terragrunt.hcl file and return its contents"""
        try:
            with open(file_path, 'r') as f:
                return hcl2.load(f)
        except Exception as e:
            self.logger.error(f"Error parsing {file_path}: {str(e)}")
            return None

    def _extract_terraform_source(self, config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract source and version from terraform block"""
        try:
            terraform_block = config.get('terraform', [{}])[0]
            if not terraform_block:
                return None

            source = None
            version = None

            # Check for source in terraform block
            if 'source' in terraform_block:
                source_value = terraform_block['source']

                # Handle if source is a list (common in HCL parsing)
                if isinstance(source_value, list):
                    source = source_value[0]
                else:
                    source = source_value

            if not source:
                return None

            # Clean up the source string
            source = str(source)

            # Handle tfr:/// format (Terraform Registry)
            if source.startswith('tfr:///'):
                # Remove the tfr:/// prefix
                source = source.replace('tfr:///', '')

                # Extract version if present
                if '?version=' in source:
                    source, version_part = source.split('?version=')
                    version = version_part

                # Clean source and create registry URL
                clean_source = source.strip('/')
                registry_url = f"https://registry.terraform.io/modules/{clean_source}/{version or 'latest'}"

                return {
                    'source': clean_source,
                    'url': registry_url,
                    'version': version,
                    'is_registry': True
                }

            # Handle other sources (like git)
            else:
                # Your existing logic for other source types
                if '/' in source:
                    module_parts = source.split('/')
                    if len(module_parts) >= 3:
                        github_url = f"github.com/{'/'.join(module_parts)}"
                        return {
                            'source': source,
                            'url': github_url,
                            'version': version,
                            'is_registry': False
                        }

            return None

        except Exception as e:
            self.logger.error(f"Error extracting terraform source: {str(e)}")
            return None

    def _get_module_description(self, config: Dict[str, Any]) -> str:
        """Extract or generate module description from config"""
        # You can enhance this to extract description from comments or other fields
        try:
            # Example: try to get description from locals or inputs
            locals_block = config.get('locals', [{}])[0]
            return locals_block.get('description', 'Terragrunt configuration for infrastructure deployment')
        except:
            return 'Terragrunt configuration for infrastructure deployment'

    def generate_info_file(self, terragrunt_path: Path) -> bool:
        """Generate .info.md file for a terragrunt.hcl file"""
        try:
            config = self._parse_terragrunt_file(terragrunt_path)
            if not config:
                return False

            source_info = self._extract_terraform_source(config)
            if not source_info:
                self.logger.warning(f"No source information found in {terragrunt_path}")
                # Create minimal info file even without source information
                info_content = f"""
# Stack {terragrunt_path.parent.name}
Terragrunt configuration for infrastructure deployment

## Configuration
This is a Terragrunt configuration file that manages infrastructure deployment.
"""
            else:
                # Get the module name from the parent directory
                module_name = terragrunt_path.parent.name

                # Create description based on the module name
                description = f"This file creates a {module_name} based on **{source_info['source']}**"

                info_content = f"""
# Stack {module_name}
{description}

## Source Module info
- **version**: = "{source_info['version'] or 'latest'}"
- **Link**: [{source_info['source']}]({source_info['url']})
"""

            # Write the info file
            info_file_path = terragrunt_path.parent / '.info.md'
            with open(info_file_path, 'w') as f:
                f.write(info_content)

            self.logger.debug(f"Generated .info.md for {terragrunt_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error generating info file for {terragrunt_path}: {str(e)}")
            return False
    def process_directory(self, directory: Path) -> Dict[str, int]:
        """Process a directory recursively to generate .info.md files"""
        stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }

        for root, _, files in os.walk(directory):
            if '.terragrunt-cache' in root:
                continue

            if 'terragrunt.hcl' in files:
                terragrunt_path = Path(root) / 'terragrunt.hcl'
                if self.generate_info_file(terragrunt_path):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1
            else:
                stats['skipped'] += 1

        return stats
