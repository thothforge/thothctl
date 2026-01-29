"""Create documentation for Infrastructure as Code projects."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, List, Union, Tuple
import logging
import subprocess
from colorama import Fore, init

# Initialize colorama for cross-platform color support
init(autoreset=True)


class CommandExecutor(Protocol):
    """Protocol for command execution."""

    def execute(self, command: List[str], cwd: Path, input_data: str = None) -> Tuple[str, str, int]:
        """
        Execute a command and return its output.

        Args:
            command: Command to execute as list of strings
            cwd: Working directory for command execution
            input_data: Optional input data to pipe to the command

        Returns:
            Tuple containing (stdout, stderr, return_code)
        """
        ...


class SubprocessExecutor:
    """Implements command execution using subprocess."""

    def execute(self, command: List[str], cwd: Path, input_data: str = None) -> Tuple[str, str, int]:
        """
        Execute a command using subprocess.

        Args:
            command: Command to execute as list of strings
            cwd: Working directory for command execution
            input_data: Optional input data to pipe to the command

        Returns:
            Tuple containing (stdout, stderr, return_code)
        """
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input=input_data)
            return_code = process.returncode

            return stdout, stderr, return_code

        except subprocess.SubprocessError as e:
            return "", str(e), 1


@dataclass
class GraphConfig:
    """Configuration for graph generation."""
    directory: Path
    suffix: str = "resources"
    project_root: Optional[Path] = None
    replace_path: Optional[Path] = None
    graph_type: str = "dot"


@dataclass
class GraphResult:
    """Result of graph generation."""
    success: bool
    content: Optional[str] = None
    path: Optional[Path] = None
    error: Optional[str] = None




class DependencyGraphGenerator:
    """Handles generation of dependency graphs."""

    def __init__(self, executor: CommandExecutor, logger: logging.Logger):
        self.executor = executor
        self.logger = logger

    def generate(self, config: GraphConfig) -> GraphResult:
        """Generate dependency graph."""
        try:
            # Validate and prepare paths
            dir_path = self._prepare_paths(config)
            if not dir_path:
                return GraphResult(success=False, error="Invalid directory path")

            if config.graph_type == "mermaid":
                # Generate mermaid diagram
                return self._generate_mermaid(dir_path)
            else:
                # Generate DOT/SVG graph
                processed_output = self._generate_graph(dir_path)
                if not processed_output:
                    return GraphResult(success=False, error="Failed to generate graph")
                return self._create_svg(dir_path, processed_output)

        except Exception as e:
            self.logger.error("Unexpected error: %s", e)
            return GraphResult(success=False, error=str(e))
    
    def _generate_mermaid(self, directory: Path) -> GraphResult:
        """Generate mermaid diagram with dependency details."""
        try:
            # Run terragrunt dag graph to get dependencies
            command = ["terragrunt", "dag", "graph", "--non-interactive"]
            stdout, stderr, return_code = self.executor.execute(command, directory)
            
            if return_code != 0:
                self.logger.error("Terragrunt command failed: %s", stderr)
                return GraphResult(success=False, error=stderr)
            
            # Process DOT content same as SVG generation (replace paths, handle ".")
            processed_stdout = self._process_graph_paths(stdout, directory)
            
            # Parse DOT graph to get nodes and edges
            nodes, edges = self._parse_dot_for_mermaid(processed_stdout)
            self.logger.debug(f"Parsed nodes: {nodes}")
            self.logger.debug(f"Parsed edges: {edges}")
            
            # Parse terragrunt.hcl files for dependency details
            dep_info = {}
            for node in nodes:
                node_path = directory / node
                hcl_file = node_path / 'terragrunt.hcl'
                self.logger.debug(f"Looking for HCL at: {hcl_file}")
                if hcl_file.exists():
                    parsed = self._parse_terragrunt_hcl(hcl_file)
                    self.logger.debug(f"Parsed dependencies for {node}: {parsed}")
                    dep_info[node] = parsed
                else:
                    self.logger.debug(f"HCL file not found: {hcl_file}")
            
            self.logger.debug(f"Final dep_info structure: {dep_info}")
            
            # Generate mermaid content
            mermaid_content = self._create_mermaid_content(nodes, edges, dep_info)
            
            # Save to file
            mermaid_path = directory / "graph.mmd"
            mermaid_path.write_text(mermaid_content)
            
            self.logger.debug("Successfully created mermaid diagram at: %s", mermaid_path)
            return GraphResult(
                success=True,
                content=mermaid_content,
                path=mermaid_path
            )
            
        except Exception as e:
            self.logger.error("Failed to create mermaid diagram: %s", e)
            return GraphResult(success=False, error=str(e))
    
    def _parse_dot_for_mermaid(self, dot_content: str) -> tuple:
        """Parse DOT content to extract nodes and edges."""
        import re
        nodes = set()
        edges = []
        
        for line in dot_content.split('\n'):
            # Match node definitions
            node_match = re.match(r'\s*"([^"]+)"\s*;', line)
            if node_match:
                nodes.add(node_match.group(1))
            
            # Match edges
            edge_match = re.match(r'\s*"([^"]+)"\s*->\s*"([^"]+)"', line)
            if edge_match:
                edges.append((edge_match.group(1), edge_match.group(2)))
        
        return list(nodes), edges
    
    def _create_mermaid_content(self, nodes: list, edges: list, dep_info: dict) -> str:
        """Create professional mermaid diagram with ThothCTL styling."""
        lines = [
            "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#e3f2fd','primaryTextColor':'#1565c0','primaryBorderColor':'#1976d2','lineColor':'#42a5f5','secondaryColor':'#fff3e0','tertiaryColor':'#f3e5f5','fontSize':'14px'}}}%%",
            "graph LR"
        ]
        
        # Classify nodes by dependency count
        node_deps = {}
        for node in nodes:
            dep_count = len(dep_info.get(node, {}))
            node_deps[node] = dep_count
        
        # Add nodes with professional styling
        for node in nodes:
            node_id = node.replace("-", "_").replace("/", "_")
            label_parts = [f"<b>{node}</b>"]
            
            # Add dependency details if available
            if node in dep_info and dep_info[node]:
                dep_labels = []
                for dep_name, dep_config in dep_info[node].items():
                    mock_keys = list(dep_config['mock_outputs'].keys()) if dep_config['mock_outputs'] else []
                    if mock_keys:
                        keys_str = ', '.join(mock_keys[:3])
                        if len(mock_keys) > 3:
                            keys_str += "..."
                        dep_labels.append(f"📥 {dep_name}: {keys_str}")
                
                if dep_labels:
                    label_parts.append("<br/><small>" + "<br/>".join(dep_labels[:2]) + "</small>")
                    if len(dep_labels) > 2:
                        label_parts.append(f"<br/><small>+{len(dep_labels)-2} more...</small>")
            
            label = "".join(label_parts)
            
            # Style based on dependency count
            if node_deps[node] == 0:
                # No dependencies - root node
                lines.append(f'    {node_id}["{label}"]:::rootNode')
            elif node_deps[node] <= 2:
                # Few dependencies
                lines.append(f'    {node_id}["{label}"]:::normalNode')
            else:
                # Many dependencies
                lines.append(f'    {node_id}["{label}"]:::complexNode')
        
        # Add edges with input labels
        for source, target in edges:
            source_id = source.replace("-", "_").replace("/", "_")
            target_id = target.replace("-", "_").replace("/", "_")
            
            # Find what inputs the source gets from target
            # source depends on target, so check source's dependencies
            edge_label = ""
            if source in dep_info:
                self.logger.debug(f"Checking edge {source} -> {target}")
                for dep_name, dep_config in dep_info[source].items():
                    # Match dependency name with target node
                    target_clean = target.replace("/", "").replace("-", "").lower()
                    dep_clean = dep_name.replace("/", "").replace("-", "").lower()
                    
                    self.logger.debug(f"  Comparing dep '{dep_name}' (clean: {dep_clean}) with target '{target}' (clean: {target_clean})")
                    
                    if dep_clean in target_clean or target_clean in dep_clean:
                        mock_keys = list(dep_config['mock_outputs'].keys()) if dep_config['mock_outputs'] else []
                        self.logger.debug(f"  Match found! Mock keys: {mock_keys}")
                        if mock_keys:
                            edge_label = ', '.join(mock_keys[:2])
                            if len(mock_keys) > 2:
                                edge_label += "..."
                        break
            
            if edge_label:
                self.logger.debug(f"Edge label: {edge_label}")
                lines.append(f'    {source_id} -->|{edge_label}| {target_id}')
            else:
                self.logger.debug(f"No edge label found for {source} -> {target}")
                lines.append(f'    {source_id} --> {target_id}')
        
        # Add professional styling classes
        lines.extend([
            "",
            "    classDef rootNode fill:#4caf50,stroke:#2e7d32,stroke-width:3px,color:#fff",
            "    classDef normalNode fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff",
            "    classDef complexNode fill:#ff9800,stroke:#e65100,stroke-width:2px,color:#fff"
        ])
        
        return '\n'.join(lines)

    def _prepare_paths(self, config: GraphConfig) -> Optional[Path]:
        """Prepare and validate paths."""
        try:
            dir_path = Path(config.directory).resolve()

            if not dir_path.exists():
                self.logger.error("Directory does not exist: %s", dir_path)
                return None

            # Find project root if not provided
            if not config.project_root:
                config.project_root = self._find_project_root(dir_path, config.suffix)

            self.logger.debug("Processing directory: %s", dir_path)
            print(f"{Fore.GREEN}Creating dependencies graph for {dir_path.name}{Fore.RESET}")

            return dir_path

        except Exception as e:
            self.logger.error("Failed to prepare paths: %s", e)
            return None

    def _find_project_root(self, directory: Path, suffix: str) -> Optional[Path]:
        """Find project root directory."""
        current = directory
        while current != current.parent:
            if (current / ".git").exists():
                return current / suffix
            current = current.parent
        return None

    def _generate_graph(self, directory: Path) -> Optional[str]:
        """Generate graph using terragrunt."""
        command = ["terragrunt", "dag","graph", "--non-interactive"]

        stdout, stderr, return_code = self.executor.execute(command, directory)

        if return_code != 0:
            self.logger.error("Terragrunt command failed: %s", stderr)
            return None

        # Process the graph content to simplify paths
        processed_content = self._process_graph_paths(stdout, directory)
        
        # Enhance graph with dependency information
        enhanced_content = self._enhance_graph_with_dependencies(processed_content, directory)
        
        return enhanced_content
    
    def _parse_terragrunt_hcl(self, hcl_path: Path) -> dict:
        """Parse a terragrunt.hcl file to extract dependency information."""
        import hcl2
        
        try:
            with open(hcl_path, 'r') as f:
                content = f.read()
                parsed = hcl2.loads(content)
                
                dependencies = {}
                if 'dependency' in parsed:
                    # hcl2 returns dependency as a list of dicts
                    for dep_block in parsed['dependency']:
                        for dep_name, dep_config in dep_block.items():
                            config_path = dep_config.get('config_path', [''])[0] if isinstance(dep_config.get('config_path'), list) else dep_config.get('config_path', '')
                            mock_outputs_list = dep_config.get('mock_outputs', [])
                            mock_outputs = mock_outputs_list[0] if mock_outputs_list else {}
                            
                            dependencies[dep_name] = {
                                'config_path': config_path,
                                'mock_outputs': mock_outputs
                            }
                
                return dependencies
        except Exception as e:
            self.logger.debug(f"Could not parse {hcl_path}: {e}")
            return {}
    
    def _enhance_graph_with_dependencies(self, dot_content: str, directory: Path) -> str:
        """Enhance DOT graph with dependency and mock_outputs information."""
        try:
            lines = dot_content.split('\n')
            enhanced_lines = []
            
            for line in lines:
                enhanced_lines.append(line)
                
                # Look for node definitions
                if '"' in line and '->' not in line and '{' not in line and '}' not in line:
                    node_name = line.strip().strip('"').strip(';').strip()
                    if node_name:
                        node_path = directory / node_name
                        hcl_file = node_path / 'terragrunt.hcl'
                        
                        if hcl_file.exists():
                            deps = self._parse_terragrunt_hcl(hcl_file)
                            
                            if deps:
                                dep_labels = []
                                for dep_name, dep_info in deps.items():
                                    mock_keys = list(dep_info['mock_outputs'].keys()) if dep_info['mock_outputs'] else []
                                    if mock_keys:
                                        dep_labels.append(f"{dep_name}: {', '.join(mock_keys[:3])}")
                                
                                if dep_labels:
                                    label_text = f"{node_name}\\n({'; '.join(dep_labels[:2])})"
                                    enhanced_lines[-1] = f'  "{node_name}" [label="{label_text}"];'
            
            return '\n'.join(enhanced_lines)
            
        except Exception as e:
            self.logger.error(f"Failed to enhance graph: {e}")
            return dot_content

    def _create_svg(self, directory: Path, graph_content: str) -> GraphResult:
        """Create SVG from graph content."""
        try:
            stdout, stderr, return_code = self.executor.execute(
                ["dot", "-Tsvg"],
                directory,
                input_data=graph_content
            )

            if return_code != 0:
                self.logger.error("Dot command failed: %s", stderr)
                return GraphResult(success=False, error=stderr)

            svg_path = directory / "graph.svg"
            svg_path.write_text(stdout)

            self.logger.debug("Successfully created graph at: %s", svg_path)
            return GraphResult(
                success=True,
                content=stdout,
                path=svg_path
            )

        except Exception as e:
            self.logger.error("Failed to create SVG: %s", e)
            return GraphResult(success=False, error=str(e))

    def _process_graph_paths(self, graph_content: str, directory: Path) -> str:
        """
        Process graph content to simplify paths using replace_path and project_root.

        Args:
            graph_content: Original graph content
            directory: Base directory for the graph

        Returns:
            Processed graph content with simplified paths
        """
        try:
            # Get required path components
            dir_path = directory.resolve()
            replace_path = dir_path.parents[2]

            # Get the project root path dynamically
            project_root = None
            current_path = dir_path
            while current_path != current_path.parent:
                if (current_path / ".git").exists():
                    project_root = f"{current_path}/resources"
                    break
                current_path = current_path.parent

            # Process the output through sed-like functionality
            processed_content = graph_content
            if replace_path:
                processed_content = processed_content.replace(str(replace_path), "")
            if project_root:
                processed_content = processed_content.replace(str(project_root), "")

            
            # Replace dot (.) with actual directory name for current stack
            # This handles the case where terragrunt graph shows "." for current directory
            stack_name = dir_path.name
            processed_content = processed_content.replace('"."', f'"{stack_name}"')
            processed_content = processed_content.replace("'.'", f"'{stack_name}'")
            # Also handle cases without quotes
            processed_content = processed_content.replace(" . ", f" {stack_name} ")
            processed_content = processed_content.replace(" .\n", f" {stack_name}\n")
            processed_content = processed_content.replace(" .;", f" {stack_name};")

            return processed_content

        except Exception as e:
            self.logger.error(f"Failed to process graph paths: {e}")
            return graph_content

    def _add_graph_styling(self, content: str) -> str:
        """
        Add styling to the graph content for better visualization.

        Args:
            content: Original graph content

        Returns:
            Styled graph content
        """
        # Split content to add global graph attributes
        lines = content.splitlines()

        # Find the digraph opening line
        for i, line in enumerate(lines):
            if line.strip().startswith('digraph'):
                # Add styling after the opening bracket
                styled_lines = lines[:i + 1] + [
                    '  // Graph styling',
                    '  graph [',
                    '    rankdir="LR",',
                    '    splines="ortho",',
                    '    nodesep=0.8,',
                    '    ranksep=1.0,',
                    '    fontname="Arial",',
                    '    fontsize=12',
                    '  ];',
                    '',
                    '  // Node styling',
                    '  node [',
                    '    shape="box",',
                    '    style="rounded,filled",',
                    '    fillcolor="#f0f0f0",',
                    '    fontname="Arial",',
                    '    fontsize=10,',
                    '    margin=0.3',
                    '  ];',
                    '',
                    '  // Edge styling',
                    '  edge [',
                    '    fontname="Arial",',
                    '    fontsize=9,',
                    '    penwidth=1.5,',
                    '    color="#666666"',
                    '  ];',
                    ''
                ] + lines[i + 1:]

                return '\n'.join(styled_lines)

        # If no digraph found, return original content
        return content


import sys


def setup_graph_generator() -> DependencyGraphGenerator:
    """
    Set up the graph generator with dependencies and configured logging.

    Returns:
        DependencyGraphGenerator: Configured generator instance
    """
    # Create logger with more detailed configuration
    logger = logging.getLogger("DependencyGraph")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers to avoid duplicate logging
    logger.handlers.clear()

    # Create console handler with colored output
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Create and return generator with configured executor
    return DependencyGraphGenerator(
        executor=SubprocessExecutor(),
        logger=logger
    )


def graph_dependencies(
        directory: Union[Path, str],
        suffix: str = "resources",
        project_root: Optional[Path] = None,
        replace_path: Optional[Path] = None,
        graph_type: str = "dot"
) -> Optional[GraphResult]:
    """
    Generate dependency graph for the specified directory.

    Args:
        directory: Path to the directory containing Terraform/Terragrunt files
        suffix: Suffix for resource paths (default: "resources")
        project_root: Optional project root path
        replace_path: Optional path to replace in the graph

    Returns:
        Optional[GraphResult]: Graph generation result or None if failed

    Raises:
        ValueError: If directory is invalid or doesn't exist
    """
    try:
        # Convert directory to Path if string
        dir_path = Path(directory)
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {dir_path}")

        # Set up generator
        generator = setup_graph_generator()

        # Create configuration
        config = GraphConfig(
            directory=dir_path,
            suffix=suffix,
            project_root=project_root,
            replace_path=replace_path,
            graph_type=graph_type
        )

        # Generate graph
        result = generator.generate(config)

        if not result.success:
            generator.logger.error(
                f"{Fore.RED}Graph generation failed: {result.error}{Fore.RESET}"
            )
            return None

        # Log success message with path
        if result.path:
            generator.logger.debug(
                f"{Fore.GREEN}Successfully generated graph at: {result.path}{Fore.RESET}"
            )

        return result

    except Exception as e:
        logging.getLogger("DependencyGraph").error(
            f"{Fore.RED}Unexpected error during graph generation: {str(e)}{Fore.RESET}"
        )
        return None


from pathlib import Path
from typing import Optional, Union, List, Generator
import logging
import sys
from colorama import Fore
import concurrent.futures
from dataclasses import dataclass


@dataclass
class RecursiveGraphResult:
    """Result container for recursive graph generation."""
    directory: Path
    result: Optional[GraphResult]
    error: Optional[str] = None


def find_terragrunt_files(
        start_path: Path,
        exclude_patterns: List[str] = None
) -> Generator[Path, None, None]:
    """
    Recursively find all terragrunt.hcl files in the given directory.

    Args:
        start_path: Directory to start searching from
        exclude_patterns: List of patterns to exclude from search

    Yields:
        Path objects for directories containing terragrunt.hcl
    """
    if exclude_patterns is None:
        exclude_patterns = ['.terraform', '.git', '.terragrunt-cache']

    try:
        for item in start_path.rglob('terragrunt.hcl'):
            # Check if parent directory should be excluded
            if not any(excluded in str(item.parent) for excluded in exclude_patterns):
                yield item.parent
    except Exception as e:
        logging.getLogger("DependencyGraph").error(
            f"{Fore.RED}Error searching for terragrunt files: {str(e)}{Fore.RESET}"
        )


def process_single_directory(
        directory: Path,
        suffix: str,
        project_root: Optional[Path] = None,
        replace_path: Optional[Path] = None,
        graph_type: str = "dot"
) -> RecursiveGraphResult:
    """
    Process a single directory for graph generation.

    Args:
        directory: Directory to process
        suffix: Suffix for resource paths
        project_root: Optional project root path
        replace_path: Optional path to replace

    Returns:
        RecursiveGraphResult containing the results or error
    """
    try:
        result = graph_dependencies(
            directory=directory,
            suffix=suffix,
            project_root=project_root,
            replace_path=replace_path,
            graph_type=graph_type
        )
        return RecursiveGraphResult(directory=directory, result=result)
    except Exception as e:
        return RecursiveGraphResult(
            directory=directory,
            result=None,
            error=str(e)
        )


def graph_dependencies_recursive(
        directory: Union[Path, str],
        suffix: str = "resources",
        project_root: Optional[Path] = None,
        replace_path: Optional[Path] = None,
        exclude_patterns: List[str] = None,
        max_workers: int = 4,
        graph_type: str = "dot"
) -> List[RecursiveGraphResult]:
    """
    Recursively generate dependency graphs for all terragrunt.hcl files.

    Args:
        directory: Root directory to start searching from
        suffix: Suffix for resource paths
        project_root: Optional project root path
        replace_path: Optional path to replace
        exclude_patterns: List of patterns to exclude from search
        max_workers: Maximum number of parallel workers

    Returns:
        List of RecursiveGraphResult objects containing results for each directory
    """
    logger = logging.getLogger("DependencyGraph")
    start_path = Path(directory)

    if not start_path.exists():
        logger.error(f"{Fore.RED}Directory does not exist: {start_path}{Fore.RESET}")
        return []

    # Find all terragrunt.hcl files
    terragrunt_dirs = list(find_terragrunt_files(start_path, exclude_patterns))

    if not terragrunt_dirs:
        logger.warning(
            f"{Fore.YELLOW}No terragrunt.hcl files found in {start_path}{Fore.RESET}"
        )
        return []

    logger.debug(
        f"{Fore.GREEN}Found {len(terragrunt_dirs)} terragrunt directories to process{Fore.RESET}"
    )

    results: List[RecursiveGraphResult] = []

    # Process directories in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_dir = {
            executor.submit(
                process_single_directory,
                directory=d,
                suffix=suffix,
                project_root=project_root,
                replace_path=replace_path,
                graph_type=graph_type
            ): d for d in terragrunt_dirs
        }

        for future in concurrent.futures.as_completed(future_to_dir):
            directory = future_to_dir[future]
            try:
                result = future.result()
                results.append(result)

                if result.error:
                    logger.error(
                        f"{Fore.RED}Error processing {directory}: {result.error}{Fore.RESET}"
                    )
                elif result.result and result.result.success:
                    logger.debug(
                        f"{Fore.GREEN}Successfully processed {directory}{Fore.RESET}"
                    )
            except Exception as e:
                logger.error(
                    f"{Fore.RED}Failed to process {directory}: {str(e)}{Fore.RESET}"
                )
                results.append(RecursiveGraphResult(
                    directory=directory,
                    result=None,
                    error=str(e)
                ))

    return results

