import re
import subprocess
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from colorama import Fore


def svg_to_dot(svg_file):
    # Parse SVG file
    tree = ET.parse(svg_file)
    root = tree.getroot()

    # Initialize DOT output
    dot_lines = [
        "digraph G {",
        "    // Graph attributes",
        "    node [shape=ellipse];",
        "",
    ]

    # Dictionary to store nodes
    nodes = {}
    edges = []

    # Find all node elements
    for g in root.findall(".//{http://www.w3.org/2000/svg}g"):
        if g.get("class") == "node":
            # Extract node title
            title = g.find(".//{http://www.w3.org/2000/svg}title")
            if title is not None:
                node_id = title.text
                # Clean node ID for DOT format
                clean_id = re.sub(r"[/\-]", "_", node_id)
                nodes[node_id] = clean_id
                dot_lines.append(f'    {clean_id} [label="{node_id}"];')

    # Find all edge elements
    for g in root.findall(".//{http://www.w3.org/2000/svg}g"):
        if g.get("class") == "edge":
            title = g.find(".//{http://www.w3.org/2000/svg}title")
            if title is not None:
                # Extract source and target from edge title
                edge_text = title.text
                if "->" in edge_text:
                    source, target = edge_text.split("->")
                    source = source.strip()
                    target = target.strip()
                    edges.append((source, target))

    # Add edges to DOT
    dot_lines.append("")
    dot_lines.append("    // Edges")
    for source, target in edges:
        if source in nodes and target in nodes:
            dot_lines.append(f"    {nodes[source]} -> {nodes[target]};")

    # Close the graph
    dot_lines.append("}")

    return "\n".join(dot_lines)


def write_dot_file(dot_content, output_file):
    with open(output_file, "w") as f:
        f.write(dot_content)


def convert_svg_to_dot(input_svg="graph.svg", output_dot="/tmp/output.dot"):
    """
    Convert SVG file to DOT format and save it to a file.

    Args:
        input_svg (str): Path to input SVG file
        output_dot (str): Path to output DOT file

    Returns:
        str: The generated DOT content if successful, None if an error occurs
    """
    try:
        dot_content = svg_to_dot(input_svg)
        write_dot_file(dot_content, output_dot)
        return dot_content
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def print_dot_graph(dot_file="/tmp/output.dot"):
    """
    Print DOT file using graph-easy with proper error handling and output capture

    Args:
        dot_file (str): Path to the DOT file
    Returns:
        bool: True if successful, False otherwise
    """

    try:
        # Print original DOT content
        print(f"{Fore.BLUE}\nDependency Graph Visualization: ")

        # Run graph-easy with proper subprocess handling
        result = subprocess.run(
            ["graph-easy", dot_file], capture_output=True, text=True, check=True
        )

        # Print the graph output
        print(f"{Fore.LIGHTCYAN_EX}{result.stdout} {Fore.RESET}")

        return True

    except FileNotFoundError:
        print("Error: graph-easy not found. Please install it using: cpan Graph::Easy")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error running graph-easy: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False


@lru_cache(maxsize=32)
def graph_terragrunt_dependencies(directory: Path = Path(".")) -> bool:
    """
    Generate a graph of Terragrunt dependencies in the specified directory.
    Results are cached for improved performance on repeated calls.

    Args:
        directory (Path): The directory to search for Terragrunt files. Defaults to the current directory.

    Returns:
        bool: True if graph was successfully generated, False otherwise.
    """
    input_svg = directory.resolve().joinpath("graph.svg")

    if not input_svg.exists():
        return False

    dot_content = convert_svg_to_dot(input_svg=input_svg)
    if dot_content:
        output_path = Path("/tmp/output.dot")
        print_dot_graph(output_path)
        return True
    return False
