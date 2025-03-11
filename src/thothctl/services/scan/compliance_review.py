"""Define kind of scanning process using tools for modular deployments."""
import logging
import subprocess
import time
from enum import Enum
from pathlib import Path, PurePath
from typing import Dict, List, Optional

import os
from colorama import Fore


class ScanTool(Enum):
    """Supported scanning tools."""

    TRIVY = "trivy"
    TFSEC = "tfsec"
    CHECKOV = "checkov"
    TERRAFORM_COMPLIANCE = "terraform-compliance"


# Constants
SCAN_COMMANDS: Dict[str, List[str]] = {
    "trivy": ["trivy", "config"],
    "tfsec": ["tfsec"],
    "checkov": ["checkov", "-d"],
    "terraform-compliance": ["terraform-compliance", "-p"],
}


def get_report_path(directory: str, reports_dir: str, extension: str) -> PurePath:
    """Generate standardized report path."""
    path = Path(directory).resolve()
    report_name = f"report_{path.parent.name}_{path.name}".replace("/", "_")
    return PurePath(os.path.join(reports_dir, f"{report_name}.{extension}"))


def run_scan_command(
    cmd: List[str], capture: bool = True
) -> subprocess.CompletedProcess:
    """Execute scan command with proper error handling."""
    try:
        return subprocess.run(cmd, capture_output=capture, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Scan failed: {e}")
        raise


def trivy_scan(directory: str, reports_dir: str, options: Optional[str] = None) -> None:
    """Run trivy scan."""
    print(Fore.GREEN + f"Running trivy scan in {directory}... " + Fore.RESET)

    cmd = [*SCAN_COMMANDS["trivy"], directory]
    if options:
        cmd.append(options)

    scan = run_scan_command(cmd)
    print(scan.stdout)

    reports_path = get_report_path(directory, reports_dir, "txt")
    with open(reports_path, "w") as f:
        subprocess.run([*SCAN_COMMANDS["trivy"], directory], stdout=f, check=True)


def tfsec_scan(directory: str, reports_dir: str, options: Optional[str] = None) -> None:
    """Run tfsec scan."""
    print(Fore.GREEN + f"Running tfsec scan in {directory}... " + Fore.RESET)

    cmd = [*SCAN_COMMANDS["tfsec"], directory]
    if options:
        cmd.append(options)

    scan = run_scan_command(cmd)
    print(scan.stdout)

    reports_path = get_report_path(directory, reports_dir, "xml")
    with open(reports_path, "w") as f:
        subprocess.run([*cmd, "-f", "junit"], stdout=f, check=True)


def checkov_scan(
    directory: str,
    reports_dir: str,
    options: Optional[str] = None,
    tftool: str = "tofu",
) -> None:
    """Run checkov scan."""
    print(Fore.GREEN + f"Running checkov scan in {directory}... " + Fore.RESET)

    tf_plan = Path(os.path.join(directory, "tfplan"))
    tf_plan_json = Path(os.path.join(directory, "tfplan.json"))

    cmd = [*SCAN_COMMANDS["checkov"], directory]
    if options:
        cmd.append(options)

    scan = run_scan_command(cmd)
    print(scan.stdout)

    if tf_plan.exists():
        subprocess.run(
            f"cd {directory} && {tftool} show -json tfplan > tfplan.json",
            shell=True,
            check=True,
        )
        cmd.extend(["-f", str(tf_plan_json)])

    reports_path = get_report_path(directory, reports_dir, "xml")
    with open(reports_path, "w") as f:
        cmd.extend(["-o", "junitxml"])
        subprocess.run(cmd, stdout=f, check=True)


def terraform_compliance_scan(
    directory: str, reports_dir: str, features_dir: str, options: Optional[str] = None
) -> None:
    """Run terraform compliance scan."""
    print(
        Fore.GREEN
        + f"Running terraform-compliance scan in {directory}... "
        + Fore.RESET
    )

    tf_plan = Path(os.path.join(directory, "tfplan.json"))
    if not tf_plan.exists():
        logging.error(f"tfplan.json not found in {directory}")
        raise FileNotFoundError(f"tfplan.json not found in {directory}")

    cmd = [*SCAN_COMMANDS["terraform-compliance"], str(tf_plan), "-f", features_dir]

    if options:
        cmd.append(options)

    reports_path = get_report_path(directory, reports_dir, "xml")
    cmd.extend(["--junit-xml", str(reports_path)])

    scan = run_scan_command(cmd)
    print(scan.stdout)


def generate_reports(
    scan_results: Dict[str, subprocess.CompletedProcess],
) -> Dict[str, str]:
    """
    Generate consolidated reports from scan results.

    Args:
        scan_results: Dictionary containing scan results for each tool

    Returns:
        Dictionary containing report paths for each tool
    """
    reports = {}
    for tool, result in scan_results.items():
        if result.returncode == 0:
            reports[tool] = "PASS"
        else:
            reports[tool] = "FAIL"
            logging.error(f"{tool} scan failed with output: {result.stderr}")

    return reports


def select_tools(tools: List[str]) -> List[ScanTool]:
    """
    Select and validate scanning tools.

    Args:
        tools: List of tool names to use

    Returns:
        List of validated ScanTool enums
    """
    selected_tools = []
    for tool in tools:
        try:
            scan_tool = ScanTool(tool.lower())
            # Verify tool is installed
            subprocess.run(
                [SCAN_COMMANDS[tool][0], "--version"], capture_output=True, check=True
            )
            selected_tools.append(scan_tool)
        except ValueError:
            logging.warning(f"Unsupported tool: {tool}")
        except subprocess.CalledProcessError:
            logging.warning(f"Tool not installed: {tool}")
        except FileNotFoundError:
            logging.warning(f"Tool not found in PATH: {tool}")

    if not selected_tools:
        raise ValueError("No valid scanning tools selected")

    return selected_tools


def run_scans(
    directory: str,
    reports_dir: str,
    tools: List[str],
    features_dir: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Run selected security scans on the specified directory.

    Args:
        directory: Directory to scan
        reports_dir: Directory to store reports
        tools: List of tools to use
        features_dir: Directory containing terraform-compliance features
        options: Dictionary of tool-specific options

    Returns:
        Dictionary containing scan results
    """
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    selected_tools = select_tools(tools)
    scan_results = {}
    options = options or {}

    for tool in selected_tools:
        try:
            if tool == ScanTool.TRIVY:
                trivy_scan(directory, reports_dir, options.get("trivy"))
            elif tool == ScanTool.TFSEC:
                tfsec_scan(directory, reports_dir, options.get("tfsec"))
            elif tool == ScanTool.CHECKOV:
                checkov_scan(directory, reports_dir, options.get("checkov"))
            elif tool == ScanTool.TERRAFORM_COMPLIANCE:
                if not features_dir:
                    raise ValueError(
                        "features_dir is required for terraform-compliance"
                    )
                terraform_compliance_scan(
                    directory,
                    reports_dir,
                    features_dir,
                    options.get("terraform-compliance"),
                )

            scan_results[tool.value] = "PASS"
        except Exception as e:
            logging.error(f"Error running {tool.value}: {str(e)}")
            scan_results[tool.value] = "FAIL"

    return generate_reports(scan_results)


def scan_root(directory, tool, reports_dir, features_dir: str = "", tftool="tofu"):
    """
    Scan root path.

    :param tftool:
    :param directory:
    :param tool:
    :param reports_dir:
    :param features_dir:
    :return:
    """
    if os.path.exists(PurePath(f"{directory}/main.tf")):
        select_tool(
            directory=directory,
            tool=tool,
            reports_dir=reports_dir,
            features_dir=features_dir,
            tftool=tftool,
        )


def select_tool(
    directory, tool, reports_dir, features_dir: str = "", options=None, tftool="tofu"
):
    """
    Select tool according to the tool selected.

    If the tool is tfsec, checkov, or terraform-compliance,
    it will scan the directory and create the report.
    If the tool is xunit-viewer, it will convert the report to html.
    If the tool is junit2html, it will convert the report to html.

    :param tftool:
    :param directory:
    :param tool:
    :param reports_dir:
    :param features_dir:
    :param options:
    :return:
    """
    if tool == "tfsec":
        tfsec_scan(directory, reports_dir=reports_dir, options=options)
    elif tool == "checkov":
        checkov_scan(directory, reports_dir=reports_dir, options=options, tftool=tftool)
    elif tool == "terraform-compliance" and os.path.exists(
        PurePath(f"{directory}/tfplan")
    ):
        terraform_compliance_scan(
            directory,
            features_dir=features_dir,
            reports_dir=reports_dir,
            options=options,
        )


def create_html_reports(directory, mode="single"):
    """
    Create html reports from xml reports.

    :param directory:
    :param mode:
    :return:
    """
    print(Fore.GREEN + "Converting Reports..." + Fore.RESET)
    # Clean folder - previous html
    ls_dir = os.listdir(directory)
    c = None

    if mode == "xunit":
        c = f'cd {directory} && xunit-viewer -r .  -o CompactReport -b https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png -t "thothctl - Compact Report" -f https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png  '  # > /dev/null
        os.popen(c, "w")

    for ll in ls_dir:
        if ll.endswith(".xml"):
            s = os.path.join(directory, ll)
            d = os.path.join(directory, ll.replace("xml", "html"))
            if mode == "single":
                c = f"junit2html  {s} {d} & > /dev/null"
            elif mode == "xunit":
                c = f'xunit-viewer -r {s} -o {d} -b https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png -t "thothctl-{ll}" -f https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png  '  # > /dev/null

            os.popen(c, "w")


def recursive_scan(
    directory, tool, reports_dir, features_dir: str = "", options=None, tftool="tofu"
):
    """
    Recursive Scan according to the tool selected.

    If the tool is tfsec, checkov, or terraform-compliance,
    it will scan the directory and create the report.
    If the tool is xunit-viewer, it will convert the report to html.
    If the tool is junit2html, it will convert the report to html.
    If the tool is tfsec, checkov, or terraform-compliance,
    it will scan the directory and create the report.
    If the tool is xunit-viewer, it will convert the report to html.
    If the tool is junit2html, it will convert the report to html.
    If the tool is tfsec, checkov, or terraform-compliance,
    it will scan the directory and create the report.
    If the tool is xunit-viewer, it will convert the report to html.
    If the tool is junit2html, it will convert the report to html.
    If the tool is tfsec, checkov, or terraform-compliance,
    it will scan the directory and create the report.

    :param options:
    :param tftool:
    :param features_dir:
    :param directory:
    :param tool:
    :param reports_dir:
    :return:
    """
    scan_root(
        directory=directory,
        tool=tool,
        reports_dir=reports_dir,
        features_dir=features_dir,
        tftool=tftool,
    )

    ls_dir = os.listdir(PurePath(directory))
    start_time = time.perf_counter()
    for ld in ls_dir:
        nested_dir = os.path.join(directory, ld)
        if os.path.isdir(nested_dir) and not ld.startswith("."):
            logging.info(f"Finding a folder {ld}...")
            recursive_scan(nested_dir, tool, reports_dir, features_dir)
            if os.path.exists(PurePath(f"{nested_dir}/main.tf")) or os.path.exists(
                PurePath(f"{nested_dir}/tfplan.json")
            ):
                print(
                    f"⚠️{Fore.GREEN}Find terraform files in {nested_dir} ...\n❇️ Scanning ... "
                    + Fore.RESET
                )
                select_tool(
                    directory=nested_dir,
                    tool=tool,
                    reports_dir=reports_dir,
                    options=options,
                    tftool=tftool,
                )

    finish_time = time.perf_counter()
    print(
        f"{Fore.GREEN}Scan finished in {finish_time - start_time} seconds {Fore.RESET}"
    )
