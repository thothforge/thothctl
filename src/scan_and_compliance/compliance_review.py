"""Define kind of scanning process using tools for modular deployments."""
import logging
import subprocess
import time
from pathlib import Path, PurePath

import os
from colorama import Fore


def tfsec_scan(directory, reports_dir, options=None):
    """
    Run tfsec scan.

    :param directory:
    :param reports_dir:
    :param options:
    :return:
    """
    print(Fore.GREEN + f"Running tfsec scan in {directory}... " + Fore.RESET)
    if options is not None:
        scan = subprocess.run(
            ["tfsec", directory, options], capture_output=True, text=True
        )
    else:
        scan = subprocess.run(["tfsec", directory], capture_output=True, text=True)
    print(scan.stdout)
    logging.info("Creating tfsec reports.")
    parent = Path(directory).resolve().parent.name
    name = Path(directory).resolve().name

    report_name = "report_" + (parent + "_" + name).replace("/", "_")
    reports_path = PurePath(os.path.join(reports_dir, f"{report_name}"))
    command = f"tfsec {directory} -f junit > {reports_path}.xml"
    report = os.popen(command)
    print(report.read())


def checkov_scan(directory, reports_dir, options=None, tftool= "tofu"):
    """
    Run checkov scan.

    :param tftool:
    :param directory:
    :param reports_dir:
    :param options:
    :return:
    """
    print(Fore.GREEN + f"Running checkov scan in {directory}... " + Fore.RESET)
    tf_plan = PurePath(os.path.join(directory, "tfplan"))
    tf_plan_json = PurePath(os.path.join(directory, "tfplan.json"))
    add_command = ""

    if options is not None:
        scan = subprocess.run(
            ["checkov", "-d", directory, options], capture_output=True, text=True
        )
    else:
        scan = subprocess.run(
            ["checkov", "-d", directory], capture_output=True, text=True
        )
    print(scan.stdout)

    if os.path.exists(PurePath(tf_plan)):
        os.system(
            f"cd {directory} && {tftool} show -json tfplan  > tfplan.json"
        )

        add_command = f"-f {tf_plan_json}"

        logging.info("Creating checkov reports.")
    parent = Path(directory).resolve().parent.name
    name = Path(directory).resolve().name

    report_name = "report_" + (parent + "_" + name).replace("/", "_")
    reports_path = PurePath(os.path.join(reports_dir, f"{report_name}.xml"))
    command = f"checkov -d {directory} {add_command} -o junitxml > {reports_path}"
    command = os.popen(command)
    print(command.read())


def terraform_compliance_scan(
    directory,
    reports_dir,
    features_dir,
    options=None,
):
    """
    Run terraform compliance scan.

    :param directory:
    :param reports_dir:
    :param options:
    :param features_dir:
    :return:
    """
    print(
        Fore.GREEN
        + f"Running terraform-compliance scan in {directory}... "
        + Fore.RESET
    )
    logging.info("Creating terraform-compliance reports.")
    parent = Path(directory).resolve().parent.name
    name = Path(directory).resolve().name

    report_name = "report_" + (parent + "_" + name).replace("/", "_")
    tf_plan_path = PurePath(os.path.join(directory, "tfplan"))
    reports_path = PurePath(os.path.join(reports_dir, f"{report_name}.xml"))
    if options is not None:
        command = f"terraform-compliance -f {features_dir} -p {tf_plan_path} --format junit  --junit-xml={reports_path} {options}"
        print(command)

    else:
        command = f"terraform-compliance -f {features_dir} -p {tf_plan_path} --format junit  --junit-xml={reports_path}.xml"
        print(command)

    command = os.popen(command)
    print(command.read())


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


def select_tool(directory, tool, reports_dir, features_dir: str = "", options=None, tftool= "tofu"):
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
        checkov_scan(directory, reports_dir=reports_dir, options=options, tftool= tftool)
    elif tool == "terraform-compliance" and os.path.exists(
        PurePath(f"{directory}/tfplan")
    ):
        terraform_compliance_scan(
            directory,
            features_dir=features_dir,
            reports_dir=reports_dir,
            options=options,
        )


def scan_root(directory, tool, reports_dir, features_dir: str = "", tftool= "tofu"):
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
            tftool=tftool
        )


def recursive_scan(directory, tool, reports_dir, features_dir: str = "", options=None, tftool = "tofu"):
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
        tftool=tftool
    )

    ls_dir = os.listdir(PurePath(directory))
    start_time = time.perf_counter()
    for ld in ls_dir:
        nested_dir = os.path.join(directory, ld)
        if os.path.isdir(nested_dir) and not ld.startswith("."):
            logging.info(f"Finding a folder {ld}...")
            recursive_scan(nested_dir, tool, reports_dir, features_dir)
            if os.path.exists(PurePath(f"{nested_dir}/main.tf")) or os.path.exists(PurePath(f"{nested_dir}/tfplan.json")):
                print(
                    f"⚠️{Fore.GREEN}Find terraform files in {nested_dir} ...\n❇️ Scanning ... "
                    + Fore.RESET
                )
                select_tool(
                    directory=nested_dir,
                    tool=tool,
                    reports_dir=reports_dir,
                    options=options,
                    tftool=tftool
                )

    finish_time = time.perf_counter()
    print(
        f"{Fore.GREEN}Scan finished in {finish_time - start_time} seconds {Fore.RESET}"
    )
