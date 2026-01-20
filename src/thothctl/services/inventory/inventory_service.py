import re
import subprocess
import shlex
"""Inventory management service."""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import hcl2

from ...utils.platform_utils import find_executable, get_executable_name
from .models import Component, ComponentGroup, Inventory, Provider
from .module_compatibility_service import ModuleCompatibilityService
from .report_service import ReportService
from .schema_compatibility_service import SchemaCompatibilityService
from .terragrunt_parser import TerragruntParser
from .update_versions import main_update_versions
from .version_service import InventoryVersionManager, ProviderVersionManager


logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing infrastructure inventory."""

    def __init__(
        self,
        version_service: Optional[InventoryVersionManager] = None,
        report_service: Optional[ReportService] = None,
        provider_version_service: Optional[ProviderVersionManager] = None,
    ):
        """Initialize inventory service."""
        self.version_service = version_service or InventoryVersionManager()
        self.report_service = report_service or ReportService()
        self.provider_version_service = provider_version_service or ProviderVersionManager()
        self.schema_compatibility_service = SchemaCompatibilityService()
        self.module_compatibility_service = ModuleCompatibilityService()
        self.terragrunt_parser = TerragruntParser()
        self.is_terragrunt_project = False

    def _parse_hcl_file(self, file_path: Path) -> List[Component]:
        """Parse HCL file and extract components."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = hcl2.load(file)
        except Exception as e:
            logger.error(f"Failed to load HCL file {file_path}: {str(e)}")
            data = {}
        components = []

        if "module" in data.keys():
            for module in data["module"]:
                for name, details in module.items():
                    source = module[name].get("source", "")
                    version = module[name].get("version", ["Null"])
                    
                    # Ensure source and version are lists
                    if not isinstance(source, list):
                        source = [source] if source else ["Null"]
                    if not isinstance(version, list):
                        version = [version] if version else ["Null"]
                    
                    component = Component(
                        type="module",
                        name=name,
                        version=version,
                        source=source,
                        file=str(file_path.relative_to(Path.cwd())),
                        status="Null"  # Keep original status logic - will be updated by version service
                    )
                    components.append(component)
        else:
            logger.debug(f"No modules found in {file_path}")
        return components

    def _is_local_module(self, source: str) -> bool:
        """
        Check if a module source is a local path.
        
        Args:
            source: The source string from the module
            
        Returns:
            True if the source is a local path, False otherwise
        """
        if not source or source == "Null":
            return False
            
        # Check for local paths
        return (source.startswith("./") or 
                source.startswith("../") or 
                source.startswith("/") or
                # Check for relative paths with multiple levels
                source.startswith("../../") or
                source.startswith("../../../") or
                source.startswith("../../../../") or
                # Check for absolute paths without protocol
                (not source.startswith("http") and not source.startswith("git") and "/" in source and not source.count("/") == 2))

    def _determine_module_status(self, source: str) -> str:
        """
        Determine the status of a module based on its source.
        
        Args:
            source: The source string from the module
            
        Returns:
            Status string: "Local", "Registry", "Git", or "Unknown"
        """
        if not source or source == "Null":
            return "Unknown"
            
        # Check for local paths
        if self._is_local_module(source):
            return "Local"
            
        # Check for Terraform Registry format (namespace/name/provider)
        if "/" in source and source.count("/") == 2 and not source.startswith("git") and not source.startswith("http"):
            # Additional check: registry modules typically don't have file extensions or deep paths
            if not source.endswith(".git") and "?" not in source:
                return "Registry"
                
        # Check for Git sources
        if (source.startswith("git::") or 
            source.startswith("git@") or
            source.endswith(".git") or
            "github.com" in source or
            "gitlab.com" in source or
            "bitbucket.org" in source):
            return "Git"
            
        # Check for HTTP sources
        if source.startswith("http://") or source.startswith("https://"):
            return "HTTP"
            
        return "Unknown"

    def _parse_terragrunt_file(self, file_path: Path, source_directory: Path = None) -> List[Component]:
        """Parse Terragrunt HCL file and extract components."""
        return self.terragrunt_parser.parse_terragrunt_file(file_path, source_directory)

    def _walk_directory(self, directory: Path, complete: bool = False) -> Generator[Tuple[str, Path], None, None]:
        """
        Walk directory and yield file type and path.
        
        Args:
            directory: Directory to walk
            complete: If True, exclude .terraform and .terragrunt-cache folders
        
        Returns:
            Generator yielding tuples of (file_type, path)
            where file_type is either 'terraform' or 'terragrunt'
        """
        # First check for terragrunt.hcl files
        terragrunt_files = []
        
        # Skip .terragrunt-cache directories when scanning for terragrunt files
        for path in directory.rglob("terragrunt.hcl"):
            # Skip files in excluded directories
            if self._should_exclude_path(path, complete):
                continue
            if path.is_file():
                terragrunt_files.append(path)
                yield ('terragrunt', path)
        
        if terragrunt_files:
            self.is_terragrunt_project = True
            logger.info(f"Found {len(terragrunt_files)} terragrunt.hcl files")
        
        # Also check for regular .tf files
        for path in directory.rglob("*.tf"):
            # Skip files in excluded directories
            if self._should_exclude_path(path, complete):
                continue
            if path.is_file():
                yield ('terraform', path)

    def _should_exclude_path(self, path: Path, complete: bool) -> bool:
        """
        Check if a path should be excluded from analysis.
        
        Args:
            path: Path to check
            complete: If True, include everything (complete analysis). If False, exclude cache folders.
            
        Returns:
            True if path should be excluded, False otherwise
        """
        # If complete flag is set, don't exclude anything (complete analysis)
        if complete:
            return False
            
        path_str = str(path)
        
        # Without complete flag, exclude both .terraform and .terragrunt-cache folders
        if ".terragrunt-cache" in path_str or ".terraform" in path_str:
            return True
            
        return False

    def _detect_project_type(self, source_path: Path, complete: bool = False) -> str:
        """
        Detect if the project is Terraform or Terragrunt based.
        
        Args:
            source_path: Path to the source directory
            complete: If True, include everything (complete analysis). If False, exclude cache folders.
            
        Returns:
            'terragrunt', 'terraform', 'terraform-terragrunt', or 'module'
        """
        has_terragrunt = False
        has_terraform = False
        
        # Check if this is a single module (has version.tf or versions.tf but no subdirectories with .tf files)
        version_files = list(source_path.glob("version*.tf"))
        if version_files:
            # Check if there are .tf files in subdirectories
            has_subdir_tf = False
            for path in source_path.rglob("*.tf"):
                if path.parent != source_path and not self._should_exclude_path(path, complete):
                    has_subdir_tf = True
                    break
            
            # If we have version.tf but no .tf files in subdirectories, it's likely a module
            if not has_subdir_tf:
                return "module"        # Check for root terragrunt.hcl
        root_terragrunt = source_path / "terragrunt.hcl"
        if root_terragrunt.exists():
            has_terragrunt = True
            
        # Check for terragrunt.hcl files in subdirectories (excluding specified folders)
        for path in source_path.rglob("terragrunt.hcl"):
            if not self._should_exclude_path(path, complete):
                has_terragrunt = True
                break
                
        # Check for .tf files (excluding specified folders)
        for path in source_path.rglob("*.tf"):
            if not self._should_exclude_path(path, complete):
                has_terraform = True
                break
            
        # Determine project type based on findings
        if has_terragrunt and has_terraform:
            return "terraform-terragrunt"
        elif has_terragrunt:
            return "terragrunt"
        else:
            return "terraform"

    async def create_inventory(
        self,
        source_directory: str = ".",
        check_versions: bool = False,
        report_type: str = "html",
        reports_directory: str = "Reports",
        framework_type: str = "auto",
        complete: bool = False,
        check_providers: bool = False,
        check_provider_versions: bool = False,
        check_schema_compatibility: bool = False,
        provider_tool: str = "tofu",
        project_name: Optional[str] = None,
        terragrunt_args: str = "",        print_console: bool = True,
    ) -> Dict[str, Any]:
        """Create inventory from source directory."""
        source_path = Path(source_directory).resolve()
        component_groups: List[ComponentGroup] = []
        processed_dirs: Set[str] = set()
        terragrunt_stacks: List[str] = []  # Track terragrunt stacks
        unique_providers: Dict[str, Provider] = {}  # Track unique providers by name+version+source

        # Use provided project name or get from directory
        if not project_name:
            # Check for root.hcl file to determine project name
            root_hcl = source_path / "root.hcl"
            if root_hcl.exists():
                project_name = source_path.name
            else:
                # Use directory name as fallback
                project_name = source_path.name

        # Detect project type
        if framework_type == "auto":
            project_type = self._detect_project_type(source_path, complete)
            logger.info(f"Auto-detected project type: {project_type}")
        else:
            project_type = framework_type
            logger.info(f"Using specified project type: {project_type}")
            
        # Set flag for terragrunt projects
        self.is_terragrunt_project = "terragrunt" in project_type

        # Handle module-specific analysis
        if project_type == "module":
            return await self._analyze_module(
                source_path=source_path,
                check_versions=check_versions,
                check_providers=check_providers,
                check_provider_versions=check_provider_versions,
                check_schema_compatibility=check_schema_compatibility,
                provider_tool=provider_tool,
                project_name=project_name,
                report_type=report_type,
                reports_directory=reports_directory,
                print_console=print_console
            )        # Collect all components and track terragrunt stacks
        for file_type, file_path in self._walk_directory(source_path, complete):
            components = []
            
            if file_type == 'terragrunt':
                # Track terragrunt stack (folder containing terragrunt.hcl)
                relative_dir = str(file_path.parent.relative_to(source_path))
                stack_path = f"./{relative_dir}" if relative_dir != "." else "./"
                if stack_path not in terragrunt_stacks:
                    terragrunt_stacks.append(stack_path)
                
                components = self._parse_terragrunt_file(file_path, source_path)
            else:  # terraform
                components = self._parse_hcl_file(file_path)

            if components:  # Only add if there are components
                relative_dir = str(file_path.parent.relative_to(source_path))
                
                # For Terragrunt projects, each terragrunt.hcl file represents a separate stack
                # For Terraform projects, group files by directory
                if file_type == 'terragrunt':
                    # Each terragrunt.hcl file is its own stack
                    stack_name = f"./{relative_dir}" if relative_dir else "./."
                    group = ComponentGroup(stack=stack_name, components=components)
                else:
                    # For Terraform files, skip if we've already processed this directory
                    if relative_dir in processed_dirs:
                        continue
                        
                    processed_dirs.add(relative_dir)
                    stack_name = f"./{relative_dir}" if relative_dir else "./."
                    group = ComponentGroup(stack=stack_name, components=components)
                
                # Check providers if requested
                if check_providers:
                    # Get absolute path to the stack directory
                    abs_stack_path = (source_path / relative_dir).resolve()
                    providers = self._get_providers_for_stack(abs_stack_path, provider_tool, terragrunt_args)
                    
                    # Update the module field for each provider to use the stack name
                    for provider in providers:
                        if not provider.module or provider.module == abs_stack_path:
                            provider.module = stack_name
                        
                        # Track unique providers by name+version+source
                        provider_key = f"{provider.name}|{provider.version}|{provider.source}"
                        if provider_key not in unique_providers:
                            unique_providers[provider_key] = provider
                    
                    if providers:
                        group.providers = providers
                        logger.info(f"Added {len(providers)} providers to stack {stack_name}")
                
                component_groups.append(group)

        # Create inventory
        inventory = Inventory(
            project_name=project_name, 
            components=component_groups,
            project_type=project_type
        )
        inventory_dict = inventory.to_dict()
        
        # Add terragrunt stacks information to inventory dict
        if project_type == "terraform-terragrunt" and terragrunt_stacks:
            inventory_dict["terragrunt_stacks"] = terragrunt_stacks
            inventory_dict["terragrunt_stacks_count"] = len(terragrunt_stacks)
        
        # Add unique providers count to inventory dict
        if check_providers:
            inventory_dict["unique_providers_count"] = len(unique_providers)
        
        # Check versions if requested
        if check_versions and inventory_dict:
            inventory_dict = await self.version_service.check_versions(inventory_dict)
            
        # Check provider versions if requested
        if check_provider_versions and check_providers and inventory_dict:
            logger.info("Checking provider versions against registries...")
            
            # Collect all providers from all component groups
            all_providers = []
            for component_group in inventory_dict.get("components", []):
                providers = component_group.get("providers", [])
                all_providers.extend(providers)
            
            if all_providers:
                # Check provider versions
                updated_providers = await self.provider_version_service.check_provider_versions(all_providers)
                
                # Update the inventory with enhanced provider information
                provider_index = 0
                for component_group in inventory_dict.get("components", []):
                    group_providers = component_group.get("providers", [])
                    if group_providers:
                        # Replace providers with updated versions
                        updated_group_providers = updated_providers[provider_index:provider_index + len(group_providers)]
                        component_group["providers"] = updated_group_providers
                        provider_index += len(group_providers)
                
                # Add provider version statistics
                outdated_providers = sum(1 for p in updated_providers if p.get("status") == "outdated")
                current_providers = sum(1 for p in updated_providers if p.get("status") == "current")
                unknown_providers = sum(1 for p in updated_providers if p.get("status") == "unknown")
                
                inventory_dict["provider_version_stats"] = {
                    "total_providers": len(updated_providers),
                    "outdated_providers": outdated_providers,
                    "current_providers": current_providers,
                    "unknown_providers": unknown_providers
                }
        
        # Debug logging for schema compatibility conditions
        logger.info(f"Schema compatibility debug: check_schema_compatibility={check_schema_compatibility}")
        logger.info(f"Schema compatibility debug: check_provider_versions={check_provider_versions}")
        logger.info(f"Schema compatibility debug: inventory_dict exists={inventory_dict is not None}")
        if inventory_dict:
            logger.info(f"Schema compatibility debug: inventory_dict has components={len(inventory_dict.get('components', []))}")
        
        # Check schema compatibility if requested
        if check_schema_compatibility and check_provider_versions and inventory_dict:
            logger.info("🔍 Starting provider schema compatibility analysis...")
            
            try:
                import asyncio
                
                # Create async wrapper function
                async def check_compatibility_async():
                    logger.info("🔍 Inside async compatibility check function")
                    # Collect unique providers with version information
                    compatibility_reports = []
                    processed_providers = set()
                    
                    logger.info(f"🔍 Processing {len(inventory_dict.get('components', []))} component groups")
                    
                    for component_group in inventory_dict.get("components", []):
                        providers = component_group.get("providers", [])
                        logger.info(f"🔍 Component group has {len(providers)} providers")
                        
                        for provider in providers:
                            provider_key = f"{provider['name']}:{provider.get('version', 'latest')}"
                            latest_version = provider.get('latest_version')
                            
                            logger.info(f"🔍 Checking provider: {provider['name']} v{provider.get('version', 'latest')}, latest: {latest_version}")
                            
                            if provider_key not in processed_providers and latest_version:
                                processed_providers.add(provider_key)
                                logger.info(f"🔍 Processing compatibility for {provider['name']}")
                                
                                # Extract namespace from provider source
                                source_value = provider.get('source', provider['name'])
                                logger.info(f"🔍 Provider source value: {source_value}")
                                namespace, provider_name = self._extract_provider_namespace(source_value)
                                logger.info(f"🔍 Extracted namespace: {namespace}, provider: {provider_name}")
                                
                                # Get resources used by this provider (optional enhancement)
                                used_resources = None  # Could be extracted from IaC files
                                
                                # Check compatibility
                                compatibility_report = await self.schema_compatibility_service.check_provider_compatibility(
                                    provider_name=provider_name,
                                    current_version=provider.get('version', 'latest'),
                                    latest_version=provider.get('latest_version', provider.get('version', 'latest')),
                                    used_resources=used_resources,
                                    namespace=namespace
                                )
                                
                                compatibility_reports.append(compatibility_report)
                                logger.info(f"🔍 Added compatibility report for {provider['name']}: {compatibility_report.compatibility_level.value}")
                            else:
                                if provider_key in processed_providers:
                                    logger.info(f"🔍 Skipping duplicate provider: {provider_key}")
                                else:
                                    logger.info(f"🔍 Skipping provider without latest_version: {provider['name']}")
                    
                    logger.info(f"🔍 Generated {len(compatibility_reports)} compatibility reports")
                    return compatibility_reports
                
                # Run async compatibility check
                compatibility_reports = await check_compatibility_async()
                
                # Add compatibility reports to inventory
                if compatibility_reports:
                    inventory_dict["schema_compatibility"] = {
                        "reports": [
                            {
                                "provider_name": report.provider_name,
                                "current_version": report.current_version,
                                "latest_version": report.latest_version,
                                "compatibility_level": report.compatibility_level.value,
                                "breaking_changes_count": len(report.breaking_changes),
                                "warnings_count": len(report.warnings),
                                "new_features_count": len(report.new_features),
                                "summary": report.summary,
                                "recommendations": report.recommendations,
                                "changelog_data": report.changelog_data,
                                "breaking_changes": [
                                    {
                                        "type": change.type,
                                        "resource": change.resource,
                                        "attribute": change.attribute,
                                        "description": change.description,
                                        "severity": change.severity,
                                        "impact": change.impact
                                    }
                                    for change in report.breaking_changes
                                ],
                                "warnings": [
                                    {
                                        "type": change.type,
                                        "resource": change.resource,
                                        "attribute": change.attribute,
                                        "description": change.description,
                                        "severity": change.severity,
                                        "impact": change.impact
                                    }
                                    for change in report.warnings
                                ]
                            }
                            for report in compatibility_reports
                        ],
                        "total_providers_analyzed": len(compatibility_reports),
                        "providers_with_breaking_changes": sum(1 for r in compatibility_reports if r.breaking_changes),
                        "providers_with_warnings": sum(1 for r in compatibility_reports if r.warnings)
                    }
                    
                    # Store full reports for HTML generation
                    inventory_dict["_compatibility_reports"] = compatibility_reports
                    
                    logger.info(f"Schema compatibility analysis completed for {len(compatibility_reports)} providers")
                    logger.info(f"Found {inventory_dict['schema_compatibility']['providers_with_breaking_changes']} providers with breaking changes")
                    logger.info(f"Found {inventory_dict['schema_compatibility']['providers_with_warnings']} providers with warnings")
                else:
                    logger.info("No providers found for schema compatibility analysis")
                
            except Exception as e:
                logger.error(f"Error during schema compatibility checking: {str(e)}")
                logger.debug(f"Schema compatibility error details: {str(e)}", exc_info=True)
                inventory_dict["schema_compatibility"] = {
                    "error": f"Schema compatibility analysis failed: {str(e)}",
                    "reports": [],
                    "total_providers_analyzed": 0,
                    "providers_with_breaking_changes": 0,
                    "providers_with_warnings": 0
                }
                
                logger.info(f"Provider version check completed: {outdated_providers} outdated, {current_providers} current, {unknown_providers} unknown")

        # Check module compatibility if schema compatibility is enabled
        if check_schema_compatibility and inventory_dict:
            logger.info("🔍 Starting module compatibility analysis...")
            try:
                inventory_dict = self.module_compatibility_service.check_inventory_modules_compatibility(inventory_dict)
                
                module_stats = inventory_dict.get("module_compatibility", {})
                logger.info(f"Module compatibility analysis completed:")
                logger.info(f"  - Total modules analyzed: {module_stats.get('total_modules_analyzed', 0)}")
                logger.info(f"  - Safe upgrades: {module_stats.get('safe_upgrades', 0)}")
                logger.info(f"  - Breaking changes: {module_stats.get('breaking_changes', 0)}")
                
            except Exception as e:
                logger.error(f"Error during module compatibility checking: {str(e)}")
                logger.debug(f"Module compatibility error details: {str(e)}", exc_info=True)
                inventory_dict["module_compatibility"] = {
                    "error": f"Module compatibility analysis failed: {str(e)}",
                    "total_modules_analyzed": 0,
                    "safe_upgrades": 0,
                    "breaking_changes": 0,
                    "reports": []
                }

        # Generate reports
        reports_path = Path(reports_directory)
        if not reports_path.is_absolute():
            reports_path = source_path / reports_path
            
        reports_path.mkdir(exist_ok=True, parents=True)
        
        if report_type in ("html", "all"):
            html_path = self.report_service.create_html_report(
                inventory_dict, 
                reports_directory=str(reports_path)
            )

        if report_type in ("json", "all"):
            self.report_service.create_json_report(
                inventory_dict,
                reports_directory=str(reports_path)
            )

        if report_type in ("cyclonedx", "all"):
            self.report_service.create_cyclonedx_report(
                inventory_dict,
                reports_directory=str(reports_path)
            )

        # Print to console if requested
        if print_console:
            self.report_service.print_inventory_console(inventory_dict)

        return inventory_dict

    def update_inventory(
        self, inventory_path: str, auto_approve: bool = False, action: str = "update"
    ):
        main_update_versions(
            inventory_file=inventory_path, auto_approve=auto_approve, action=action
        )
        
    def _get_providers_for_stack(self, stack_path: str, provider_tool: str = "tofu", terragrunt_args: str = "") -> List[Provider]:
        """
        Get provider information for a stack by running the provider tool.
        
        Args:
            stack_path: Path to the stack directory
            provider_tool: Tool to use for checking providers (tofu or terraform)
            terragrunt_args: Additional arguments to pass to terragrunt commands
            
        Returns:
            List of Provider objects
        """
        providers = []
        
        # Convert relative path to absolute
        abs_stack_path = Path(stack_path).resolve()
        
        if not abs_stack_path.exists() or not abs_stack_path.is_dir():
            logger.warning(f"Stack path does not exist or is not a directory: {stack_path}")
            return providers
        
        # Determine the command to use based on project type
        if self.is_terragrunt_project:
            # For Terragrunt projects, use terragrunt run providers
            command = ["terragrunt", "run"]
            
            # Add custom terragrunt arguments if provided (after 'run')
            if terragrunt_args.strip():
                # Split the arguments string and add them to the command
                # Handle both space-separated and quoted arguments
                try:
                    args = shlex.split(terragrunt_args)
                    command.extend(args)
                except ValueError:
                    # If shlex fails, split by spaces as fallback
                    args = terragrunt_args.split()
                    command.extend(args)
            
            # Add the providers command
            command.append("providers")
            tool_name = "terragrunt"
        else:
            # For regular Terraform projects, use the specified provider tool
            command = [provider_tool, "providers"]
            tool_name = provider_tool
            
        # Check if the tool exists
        try:
            # Use 'which' on Unix/Linux or 'where' on Windows
            subprocess.run(
                ["which", tool_name] if os.name != "nt" else ["where", tool_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,  # Add a timeout to prevent hanging
            )
        except subprocess.CalledProcessError:
            logger.warning(f"{tool_name} command not found. Skipping provider check.")
            return providers
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking for {tool_name} command. Skipping provider check.")
            return providers
            
        # Run the providers command
        try:
            logger.info(f"Running {' '.join(command)} in {abs_stack_path}")
            
            # Run the providers command
            result = subprocess.run(
                command,
                cwd=abs_stack_path,
                env=os.environ.copy(),  # Pass environment variables including WORKSPACE
                check=False,  # Don't raise exception on non-zero exit
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,  # Longer timeout for terragrunt
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to get providers for {stack_path}")
                logger.warning(f"Command: {' '.join(command)}")
                logger.warning(f"Return code: {result.returncode}")
                logger.warning(f"STDERR: {result.stderr}")
                logger.warning(f"STDOUT: {result.stdout}")
                return providers
                
            # Get the stack name from the path
            stack_name = str(abs_stack_path)
            
            # Parse the output and set the stack path as the module for root-level providers
            providers = self._parse_providers_output(result.stdout, stack_name)
            
            # Clean up module paths to show just the module name
            for provider in providers:
                # If the module is a full path, extract just the module name
                if provider.module and (provider.module.startswith('/') or '/' in provider.module):
                    # Extract the basename from the path for the component
                    if not provider.component:
                        provider.component = os.path.basename(provider.module)
                    provider.module = "Root"
                elif provider.module and "module." in provider.module:
                    # If it's a module reference, extract just the module name without the path
                    module_name = provider.module.split('.')[-1] if '.' in provider.module else provider.module
                    # Set the component to the module name if component is empty
                    if not provider.component:
                        provider.component = module_name
                elif not provider.module:
                    # If module is empty, set it to "Root"
                    provider.module = "Root"
                    
                # If component is still empty, use the module name
                if not provider.component and provider.module != "Root":
                    provider.component = provider.module
            
            logger.info(f"Found {len(providers)} providers in {stack_path}")
            for provider in providers:
                logger.info(f"  Provider: {provider.name}, Version: {provider.version}, Source: {provider.source}, Module: {provider.module}")
            return providers
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout while getting providers for {stack_path}")
        except Exception as e:
            logger.warning(f"Error getting providers for {stack_path}: {str(e)}")
            
        return providers
        

    def _extract_provider_namespace(self, source: str) -> tuple:
        """
        Extract namespace and provider name from source string.
        
        Args:
            source: Provider source (e.g., 'registry.terraform.io/hashicorp/aws' or 'spotinst/spotinst')
            
        Returns:
            Tuple of (namespace, provider_name)
        """
        # Remove registry prefix if present
        if '/' in source:
            parts = source.split('/')
            if len(parts) >= 2:
                # Last part is provider name, second-to-last is namespace
                provider_name = parts[-1]
                namespace = parts[-2]
                return (namespace, provider_name)
        
        # Fallback: assume hashicorp
        return ('hashicorp', source)

    def _parse_providers_output(self, output: str, stack_path: str = "") -> List[Provider]:
        """
        Parse the output of terraform/tofu providers command.
        
        Args:
            output: Output of the providers command
            stack_path: Path to the stack directory
            
        Returns:
            List of Provider objects
        """
        providers = []
        current_module = ""
        current_component = ""
        
        # Example output:
        # Providers required by configuration:
        # .
        # ├── provider[registry.opentofu.org/hashicorp/aws]
        # ├── provider[registry.opentofu.org/hashicorp/random]
        # └── module.vpc
        #     └── provider[registry.opentofu.org/hashicorp/aws]
        
        # Regular expressions to match provider lines and module headers
        provider_pattern = r'[├└]── provider\[(.*?)\](?:\s*(?:~>|>=|==|!=|<=|<|>)?\s*([\d\.]+))?'
        module_pattern = r'[├└]── module\.([^:]+)'
        
        # Additional pattern to identify component information
        # This will look for resource or data source declarations in the output
        component_pattern = r'^\s*(?:resource|data)\s+"([^"]+)"\s+"([^"]+)"'
        
        # Track indentation to determine module hierarchy
        current_indent = 0
        module_stack = []
        
        for line in output.splitlines():
            # Skip empty lines and headers
            if not line.strip() or "Providers required by configuration" in line:
                continue
                
            # Calculate indentation level
            indent = len(line) - len(line.lstrip())
            
            # If we're going back up in the hierarchy
            if indent < current_indent:
                # Pop modules from the stack until we're at the right level
                while module_stack and indent <= current_indent:
                    module_stack.pop()
                    if module_stack:
                        current_indent = indent
                    else:
                        current_indent = 0
                        current_module = ""
            
            # Check if this is a module header
            module_match = re.search(module_pattern, line)
            if module_match:
                module_name = module_match.group(1)
                current_module = f"module.{module_name}"
                module_stack.append(current_module)
                current_indent = indent
                continue
            
            # Check if this is a component (resource or data source)
            component_match = re.search(component_pattern, line)
            if component_match:
                resource_type = component_match.group(1)
                resource_name = component_match.group(2)
                current_component = f"{resource_type}.{resource_name}"
                continue
                
            # Check if this is a provider line
            provider_match = re.search(provider_pattern, line)
            if provider_match:
                source = provider_match.group(1)
                name = source.split('/')[-1]  # Extract name from source
                
                # Version might be None if not specified in the output
                version = provider_match.group(2) if provider_match.group(2) else "latest"
                
                # Use the current module (which could be the stack path for root-level providers)
                module_name = current_module
                
                # If we're in a module hierarchy, use the full path
                if module_stack:
                    module_name = ".".join(module_stack)
                
                # Extract just the module name without the full path
                component_name = current_component
                if not module_name and stack_path:
                    # Extract just the last part of the path as the component
                    component_name = os.path.basename(stack_path)
                    # Use "Root" as the module name for root-level providers
                    module_name = "Root"
                elif module_name:
                    # If we have a module name but no component, use the module name as the component
                    if not component_name:
                        # Extract just the module name without the "module." prefix
                        if "module." in module_name:
                            component_name = module_name.split('.')[-1]
                        else:
                            component_name = module_name
                
                # Try to extract component information from the line itself
                # Some provider outputs might include the resource directly in the line
                inline_component_match = re.search(r'for\s+(resource|data)\s+"([^"]+)"\s+"([^"]+)"', line)
                if inline_component_match:
                    resource_type = inline_component_match.group(2)
                    resource_name = inline_component_match.group(3)
                    component_name = f"{resource_type}.{resource_name}"
                
                providers.append(Provider(
                    name=name,
                    version=version,
                    source=source,
                    module=module_name,
                    component=component_name,
                ))
                
        return providers
    async def _analyze_module(
        self,
        source_path: Path,
        check_versions: bool = False,
        check_providers: bool = False,
        check_provider_versions: bool = False,
        check_schema_compatibility: bool = False,
        provider_tool: str = "tofu",
        project_name: Optional[str] = None,
        report_type: str = "html",
        reports_directory: str = "Reports",
        print_console: bool = False
    ) -> dict:
        """
        Analyze a single Terraform module.
        
        Args:
            source_path: Path to the module directory
            check_versions: Whether to check for latest versions
            check_providers: Whether to check provider information
            check_provider_versions: Whether to check provider versions
            check_schema_compatibility: Whether to check schema compatibility
            provider_tool: Tool to use for provider operations
            project_name: Custom project name
            report_type: Type of report to generate
            reports_directory: Directory for reports
            print_console: Whether to print to console
            
        Returns:
            Dictionary containing module analysis results
        """
        logger.info(f"🔍 Analyzing Terraform module at: {source_path}")
        
        # Parse module files to extract resources and providers
        components = []
        providers = []
        resources = []
        
        # Find all .tf files in the module
        tf_files = list(source_path.glob("*.tf"))
        
        for tf_file in tf_files:
            file_components = self._parse_hcl_file(tf_file)
            components.extend(file_components)
            
            # Extract resources from the file
            file_resources = self._extract_resources_from_file(tf_file)
            resources.extend(file_resources)
        
        # Get providers if requested
        if check_providers:
            try:
                providers = self._get_providers_for_stack(source_path, provider_tool, "")
                logger.info(f"Found {len(providers)} providers in module")
            except Exception as e:
                logger.warning(f"Could not get providers for module: {e}")
        
        # Create component group for the module
        module_name = source_path.name
        component_group = ComponentGroup(
            stack=f"./{module_name}",
            components=components,
            providers=providers
        )
        
        # Create inventory
        inventory = Inventory(
            project_name=project_name or module_name,
            components=[component_group],
            project_type="module"
        )
        
        inventory_dict = inventory.to_dict()
        
        # Add module-specific metadata
        inventory_dict["module_name"] = module_name
        inventory_dict["module_path"] = str(source_path)
        inventory_dict["resources"] = resources
        
        # Check versions if requested
        if check_versions and components:
            logger.info("🔍 Checking component versions...")
            try:
                inventory_dict = await self.provider_version_service.check_versions(
                    inventory_dict, 
                    check_provider_versions=check_provider_versions
                )
            except Exception as e:
                logger.error(f"Error checking versions: {e}")
        
        # Check provider versions if requested
        if check_provider_versions and providers:
            logger.info("🔍 Checking provider versions...")
            try:
                # Convert providers to dict format expected by the service
                provider_dicts = []
                for provider in providers:
                    provider_dict = provider.to_dict()
                    # Ensure we have the right format for version checking
                    if provider_dict.get('source') and provider_dict.get('name'):
                        provider_dicts.append(provider_dict)
                        logger.debug(f"Provider dict for version check: {provider_dict}")
                
                if provider_dicts:
                    updated_providers = await self.provider_version_service.check_provider_versions(provider_dicts)
                    logger.debug(f"Updated providers from version service: {updated_providers}")
                    
                    # Update the component group with enhanced provider information
                    enhanced_providers = []
                    for p in updated_providers:
                        logger.debug(f"Processing updated provider: {p}")
                        enhanced_providers.append(Provider(
                            name=p.get('name', ''),
                            version=p.get('version', ''),
                            source=p.get('source', ''),
                            module=p.get('module', ''),
                            component=p.get('component', ''),
                            latest_version=p.get('latest_version', 'Null'),
                            source_url=p.get('source_url', 'Null'),
                            status=p.get('status', 'Unknown')
                        ))
                    
                    component_group.providers = enhanced_providers
                    
                    # Recreate inventory with updated providers
                    inventory = Inventory(
                        project_name=project_name or module_name,
                        components=[component_group],
                        project_type="module"
                    )
                    inventory_dict = inventory.to_dict()
                    inventory_dict["module_name"] = module_name
                    inventory_dict["module_path"] = str(source_path)
                    inventory_dict["resources"] = resources
                
            except Exception as e:
                logger.error(f"Error checking provider versions: {e}")
                logger.debug(f"Provider version check error details: {e}", exc_info=True)
        
        # Check schema compatibility if requested
        if check_schema_compatibility and inventory_dict:
            logger.info("🔍 Starting schema compatibility analysis...")
            try:
                inventory_dict = await self.schema_compatibility_service.check_inventory_providers_compatibility(
                    inventory_dict, provider_tool
                )
            except Exception as e:
                logger.error(f"Error during schema compatibility checking: {e}")
        
        # Generate reports
        if reports_directory:
            try:
                reports_path = Path(reports_directory)
                reports_path.mkdir(exist_ok=True, parents=True)
                
                if report_type in ("html", "all"):
                    html_path = self.report_service.create_html_report(
                        inventory_dict, 
                        reports_directory=str(reports_path)
                    )

                if report_type in ("json", "all"):
                    self.report_service.create_json_report(
                        inventory_dict,
                        reports_directory=str(reports_path)
                    )
                    
            except Exception as e:
                logger.error(f"Error generating reports: {e}")

        # Print to console if requested (after reports are generated)
        if print_console:
            self.report_service.print_inventory_console(inventory_dict)
        
        return inventory_dict
    def _extract_resources_from_file(self, file_path: Path) -> list:
        """Extract resource definitions from a Terraform file."""
        resources = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple regex to find resource blocks
            import re
            resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{'
            matches = re.findall(resource_pattern, content)
            
            for resource_type, resource_name in matches:
                resources.append({
                    "type": "resource",
                    "resource_type": resource_type,
                    "name": resource_name,
                    "file": file_path.name
                })
                
        except Exception as e:
            logger.warning(f"Could not parse resources from {file_path}: {e}")
            
        return resources
