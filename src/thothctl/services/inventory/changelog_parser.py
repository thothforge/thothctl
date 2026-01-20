"""
Enhanced Provider Changelog Parser

Fetches and parses provider CHANGELOG files from GitHub to extract:
- Breaking changes
- Deprecations
- Upgrade guides
- Version-specific notes
"""

import re
import logging
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChangelogEntry:
    """Represents a changelog entry"""
    version: str
    type: str  # 'breaking', 'deprecated', 'note', 'feature', 'bug_fix'
    description: str
    category: Optional[str] = None  # 'resource', 'data_source', 'provider'
    resource_name: Optional[str] = None


class ProviderChangelogParser:
    """Parser for Terraform provider CHANGELOG files"""
    
    # Known provider GitHub repositories
    PROVIDER_REPOS = {
        'aws': 'hashicorp/terraform-provider-aws',
        'azurerm': 'hashicorp/terraform-provider-azurerm',
        'google': 'hashicorp/terraform-provider-google',
        'kubernetes': 'hashicorp/terraform-provider-kubernetes',
        'azuread': 'hashicorp/terraform-provider-azuread',
        'helm': 'hashicorp/terraform-provider-helm',
        'vault': 'hashicorp/terraform-provider-vault',
        'random': 'hashicorp/terraform-provider-random',
        'null': 'hashicorp/terraform-provider-null',
        'local': 'hashicorp/terraform-provider-local',
        'tls': 'hashicorp/terraform-provider-tls',
        'time': 'hashicorp/terraform-provider-time',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ThothCTL/0.9.2 Changelog Parser'
        })
    
    def get_changelog_url(self, provider_name: str, namespace: str = 'hashicorp') -> Optional[str]:
        """
        Get GitHub raw CHANGELOG URL for a provider
        
        Args:
            provider_name: Provider name (e.g., 'aws', 'datadog')
            namespace: Provider namespace (default: 'hashicorp')
        """
        # Check hardcoded list first (faster)
        repo = self.PROVIDER_REPOS.get(provider_name)
        
        if not repo:
            # Try to discover from Terraform Registry
            logger.info(f"Provider {provider_name} not in known list, discovering from registry...")
            repo = self._discover_provider_repo(provider_name, namespace)
        
        if not repo:
            # Fallback to common pattern
            logger.debug(f"Using fallback pattern for {provider_name}")
            repo = f'{namespace}/terraform-provider-{provider_name}'
        
        return f'https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md'
    
    def _discover_provider_repo(self, provider_name: str, namespace: str) -> Optional[str]:
        """
        Discover provider GitHub repository from Terraform Registry
        
        Args:
            provider_name: Provider name
            namespace: Provider namespace
            
        Returns:
            GitHub repository path (e.g., 'hashicorp/terraform-provider-aws')
        """
        try:
            # Query Terraform Registry API for provider info
            registry_url = f'https://registry.terraform.io/v1/providers/{namespace}/{provider_name}'
            logger.debug(f"Querying registry: {registry_url}")
            
            response = self.session.get(registry_url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract source URL
            source = data.get('source')
            if source:
                # Parse GitHub URL: https://github.com/hashicorp/terraform-provider-aws
                if 'github.com' in source:
                    # Extract org/repo from URL
                    parts = source.rstrip('/').split('github.com/')[-1].split('/')
                    if len(parts) >= 2:
                        repo = f'{parts[0]}/{parts[1]}'
                        logger.info(f"Discovered repository for {provider_name}: {repo}")
                        return repo
            
            logger.warning(f"Could not extract GitHub repo from source: {source}")
            return None
            
        except requests.RequestException as e:
            logger.warning(f"Failed to discover provider repo for {provider_name}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse registry response for {provider_name}: {e}")
            return None
    
    def fetch_changelog(self, provider_name: str, namespace: str = 'hashicorp') -> Optional[str]:
        """Fetch CHANGELOG content from GitHub with fallback locations"""
        repo = self.PROVIDER_REPOS.get(provider_name)
        if not repo:
            repo = self._discover_provider_repo(provider_name, namespace)
        if not repo:
            repo = f'{namespace}/terraform-provider-{provider_name}'
        
        # Try multiple common CHANGELOG locations
        changelog_paths = [
            'CHANGELOG.md',
            'CHANGELOG',
            'CHANGES.md',
            'HISTORY.md',
            'docs/CHANGELOG.md'
        ]
        
        for path in changelog_paths:
            try:
                url = f'https://raw.githubusercontent.com/{repo}/main/{path}'
                logger.debug(f"Trying changelog at: {url}")
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                logger.info(f"Successfully fetched changelog from: {url}")
                return response.text
                
            except requests.RequestException:
                # Try master branch as fallback
                try:
                    url = f'https://raw.githubusercontent.com/{repo}/master/{path}'
                    logger.debug(f"Trying changelog at: {url}")
                    
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    
                    logger.info(f"Successfully fetched changelog from: {url}")
                    return response.text
                except requests.RequestException:
                    continue
        
        logger.warning(f"Failed to fetch changelog for {provider_name} from any location")
        return None
    
    def get_upgrade_guide_url(self, provider_name: str, major_version: str, namespace: str = 'hashicorp') -> Optional[str]:
        """Get upgrade guide URL for major version"""
        return f'https://registry.terraform.io/providers/{namespace}/{provider_name}/latest/docs/guides/version-{major_version}-upgrade'
    
    def parse_version_range(
        self, 
        changelog: str, 
        from_version: str, 
        to_version: str
    ) -> List[ChangelogEntry]:
        """
        Parse changelog entries between two versions
        
        Args:
            changelog: Full CHANGELOG content
            from_version: Starting version (current)
            to_version: Target version (latest)
            
        Returns:
            List of relevant changelog entries
        """
        entries = []
        
        # Extract version sections
        version_pattern = r'^##\s+(\d+\.\d+\.\d+(?:-\w+)?)\s*(?:\(.*?\))?$'
        lines = changelog.split('\n')
        
        current_version = None
        current_section = []
        in_range = False
        
        for line in lines:
            version_match = re.match(version_pattern, line, re.MULTILINE)
            
            if version_match:
                # Process previous section
                if current_version and in_range and current_section:
                    entries.extend(self._parse_version_section(current_version, current_section))
                
                current_version = version_match.group(1)
                current_section = []
                
                # Check if we're in the version range
                if self._is_version_in_range(current_version, from_version, to_version):
                    in_range = True
                    logger.debug(f"Processing version {current_version}")
                elif self._version_less_than(current_version, from_version):
                    # Stop when we reach versions older than from_version
                    break
            elif in_range:
                current_section.append(line)
        
        # Process last section
        if current_version and in_range and current_section:
            entries.extend(self._parse_version_section(current_version, current_section))
        
        return entries
    
    def _parse_version_section(self, version: str, lines: List[str]) -> List[ChangelogEntry]:
        """Parse a single version section"""
        entries = []
        current_type = None
        current_category = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if line.upper().startswith('BREAKING CHANGE'):
                current_type = 'breaking'
                continue
            elif line.upper().startswith('DEPRECAT'):
                current_type = 'deprecated'
                continue
            elif line.upper().startswith('NOTE'):
                current_type = 'note'
                continue
            elif line.upper().startswith('FEATURE'):
                current_type = 'feature'
                continue
            elif line.upper().startswith('BUG FIX'):
                current_type = 'bug_fix'
                continue
            
            # Detect category headers
            if line.startswith('**') and line.endswith('**'):
                current_category = line.strip('*').lower()
                continue
            
            # Parse bullet points
            if line.startswith('*') or line.startswith('-'):
                description = line.lstrip('*-').strip()
                
                # Extract resource name if present
                resource_match = re.search(r'`([a-z_]+)`', description)
                resource_name = resource_match.group(1) if resource_match else None
                
                # Determine type from content if not set
                if not current_type:
                    if any(keyword in description.lower() for keyword in ['breaking', 'removed', 'incompatible']):
                        current_type = 'breaking'
                    elif any(keyword in description.lower() for keyword in ['deprecat', 'will be removed']):
                        current_type = 'deprecated'
                    else:
                        current_type = 'note'
                
                entries.append(ChangelogEntry(
                    version=version,
                    type=current_type or 'note',
                    description=description,
                    category=current_category,
                    resource_name=resource_name
                ))
        
        return entries
    
    def _is_version_in_range(self, version: str, from_version: str, to_version: str) -> bool:
        """Check if version is between from_version and to_version"""
        try:
            v = self._parse_version(version)
            v_from = self._parse_version(from_version)
            v_to = self._parse_version(to_version)
            
            return v_from < v <= v_to
        except:
            return False
    
    def _version_less_than(self, v1: str, v2: str) -> bool:
        """Check if v1 < v2"""
        try:
            return self._parse_version(v1) < self._parse_version(v2)
        except:
            return False
    
    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse version string to tuple for comparison"""
        # Remove 'v' prefix if present
        version = version.lstrip('v')
        
        # Extract major.minor.patch
        match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
        raise ValueError(f"Invalid version format: {version}")
    
    def get_breaking_changes_summary(
        self, 
        provider_name: str, 
        from_version: str, 
        to_version: str,
        namespace: str = 'hashicorp'
    ) -> Dict:
        """
        Get comprehensive breaking changes summary
        
        Args:
            provider_name: Provider name (e.g., 'aws', 'datadog')
            from_version: Current version
            to_version: Target version
            namespace: Provider namespace (default: 'hashicorp')
        
        Returns:
            Dict with breaking changes, deprecations, notes, and upgrade guide URL
        """
        changelog = self.fetch_changelog(provider_name, namespace)
        
        if not changelog:
            return {
                'available': False,
                'error': 'Could not fetch CHANGELOG',
                'changelog_url': self.get_changelog_url(provider_name, namespace)
            }
        
        entries = self.parse_version_range(changelog, from_version, to_version)
        
        # Categorize entries
        breaking_changes = [e for e in entries if e.type == 'breaking']
        deprecations = [e for e in entries if e.type == 'deprecated']
        notes = [e for e in entries if e.type == 'note']
        
        # Get major version for upgrade guide
        try:
            major_version = self._parse_version(to_version)[0]
            upgrade_guide_url = self.get_upgrade_guide_url(provider_name, str(major_version), namespace)
        except:
            upgrade_guide_url = None
        
        return {
            'available': True,
            'changelog_url': self.get_changelog_url(provider_name, namespace),
            'upgrade_guide_url': upgrade_guide_url,
            'versions_analyzed': {
                'from': from_version,
                'to': to_version,
                'count': len(set(e.version for e in entries))
            },
            'breaking_changes': [
                {
                    'version': e.version,
                    'description': e.description,
                    'resource': e.resource_name,
                    'category': e.category
                }
                for e in breaking_changes
            ],
            'deprecations': [
                {
                    'version': e.version,
                    'description': e.description,
                    'resource': e.resource_name,
                    'category': e.category
                }
                for e in deprecations
            ],
            'important_notes': [
                {
                    'version': e.version,
                    'description': e.description,
                    'resource': e.resource_name,
                    'category': e.category
                }
                for e in notes[:10]  # Limit to top 10 notes
            ],
            'summary': self._generate_summary(breaking_changes, deprecations, notes)
        }
    
    def _generate_summary(
        self, 
        breaking: List[ChangelogEntry], 
        deprecated: List[ChangelogEntry],
        notes: List[ChangelogEntry]
    ) -> str:
        """Generate human-readable summary"""
        parts = []
        
        if breaking:
            parts.append(f"⚠️ {len(breaking)} breaking change(s)")
        
        if deprecated:
            parts.append(f"📋 {len(deprecated)} deprecation(s)")
        
        if notes:
            parts.append(f"📝 {len(notes)} important note(s)")
        
        if not parts:
            return "✅ No breaking changes or deprecations found"
        
        return " | ".join(parts)
