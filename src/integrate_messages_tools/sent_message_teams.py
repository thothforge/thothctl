"""Compliance review steps and functions to get summaries and process reports."""
import datetime
import json
import logging
import time

import os
import pdfkit
import pymsteams
import xmltodict
from colorama import Fore
from json2html import json2html


def read_last_lines(filename, no_of_lines=1):
    """Read last lines of a file.

    :param filename:
    :param no_of_lines:
    :return:
    """
    sumary = ""
    text = ""
    file = open(filename, "r", encoding="utf-8")
    lines = file.readlines()
    last_lines = lines[-no_of_lines:]
    for line in last_lines:
        sumary = sumary + line
    first_lines = lines[:-no_of_lines]
    for f in first_lines:
        text = text + f

    file.close()
    text = text.replace("", " ")
    return sumary, text


def message_style(message):
    """Set message style.

    :param message
    """
    if "Approve" in message:
        color = "DarkGreen"
    elif "Skipping" in message:
        color = "SteelBlue"
    else:
        color = "FireBrick"

    output = (
        '<!DOCTYPE html> \
                                                <html> \
                                                <head> \
                                                <style> \
                                                p { \
                                                  border-style: solid; \
                                                  border-color: blue; \
                                                }\
                                                </style>\
                                                </head>\
                                                <body > \
                                                \
                                                <p style="background-color:'
        + color
        + ';color:white;padding:2%;"> <b>'
        + message
        + "</b></p>\
                            \
                            \
                            \
                            </p>\
                            \
                            </body>\
                            </html> \
                            "
    )
    return output


def check_result(failures, mod, l_type, l_tests):
    """
    Check the result of the scan and return a message.

    :param failures:
    :param mod:
    :param l_type:
    :return:
    """
    # print(failures, tests)
    if int(failures) == 0 and int(l_tests == 0):
        message = f"The are no Rules for {mod}, Skipping {l_type} Scanning"
    elif int(failures) == 0 and int(l_tests > 0):
        message = f"The  {mod}, Approve {l_type} Scanning"
    else:
        message = f"The {mod} Reprobate {l_type} Scanning"

    return message


date_test = datetime.datetime.now().strftime("%y-%m-%d-%H-%M")


def scan_checkov_reports(data, mod, report_tool):
    """
    Scan Checkov reports based on format and results.

    :param data:
    :param mod:
    :param report_tool:
    :return:
    """
    fails = 0
    tests = 0

    try:
        fails = int(data["testsuites"]["@failures"])
        tests = int(data["testsuites"]["@tests"])

        message = check_result(fails, mod, l_type="Checkov", l_tests=tests)
        output = message_style(message=message)
        print(Fore.GREEN + message + Fore.RESET)

    except Exception as err:
        logging.warning(err)
        try:
            fails = 0
            tests = 0
            for t in data["testsuites"]["testsuite"]:
                # print(t['@failures'])
                fails += int(t["@failures"])
                tests += int(t["@tests"])

            message = check_result(fails, mod, l_type="Checkov", l_tests=tests)
            output = message_style(message=message)

        except Exception as err:
            logging.warning(err)
            print(Fore.GREEN + f"No Rules for {mod} using {report_tool}" + Fore.RESET)
            message = f"No Rules for {mod} using {report_tool}"
            output = message_style(message=message)
    return output, fails, tests, message


# create tfsec check reports
def scan_tfsec_reports(data, mod, report_tool):
    """
    Scan reports when tool is tfsec and reports format.

    :param data:
    :param mod:
    :param report_tool:
    :return:

    """
    fails = 0
    tests = 0
    try:
        fails = int(data["testsuite"]["@failures"])
        tests = int(data["testsuite"]["@tests"])

        message = check_result(fails, mod, l_type="TFsec", l_tests=tests)
        output = message_style(message=message)
        print(message)

    except Exception as err:
        print(f"No Rules for {mod} using {report_tool}")
        message = f"No Rules for {mod} using {report_tool}"
        output = message_style(message=message)
        logging.warning(err)

    return output, fails, tests, message


def scan_terraform_compliance_reports(data, mod, report_tool):
    """
    Scan terraform compliance reports.

    :param data:
    :param mod:
    :param report_tool:
    :return:
    """
    fails = 0
    tests = 0
    try:
        for t in data["testsuites"]["testsuite"]:
            # print(t['@failures'])
            fails += int(t["@failures"])
            tests += int(t["@tests"])

        message = check_result(fails, mod, l_type="terraform-compliance", l_tests=tests)
        output = message_style(message=message)

    except Exception as err:
        print(f"No Rules for using {report_tool}")
        message = f"No Rules for {mod} using {report_tool}"
        output = message_style(message=message)
        logging.warning(err)

    return output, fails, tests, message


def terratest_scan_reports(data, mod, report_tool):
    """
    Scan terratest reports.

    :param data:
    :param mod:
    :param report_tool:
    :return:
    """
    fails = 0
    tests = 0
    print("Validate tests for terratest")
    try:
        # print(d['testsuites']['testsuite']['@failures'])
        # for t in d['testsuites']['testsuite']:
        t = data["testsuites"]["testsuite"]
        fails = int(t["@failures"])
        tests = int(t["@tests"])
        print(t["@failures"])
        message = check_result(fails, mod, l_type="Terratest", l_tests=tests)
        output = message_style(message=message)
        print(message)

        # Create custom message summary
        print(f"the module is {mod}")

    except Exception as err:
        print(f"No Rules for {mod} using {report_tool}")
        message = f"No Rules for {mod} using {report_tool}"
        output = message_style(message=message)
        print(err)

    return output, fails, tests, message


def scan_reports(report_tool, pathfile, mod):
    """
    Scan reports according to specific tool and format.

    :param report_tool:
    :param pathfile:
    :param mod:
    :return:
    """
    output = ""
    fails = 0
    tests = 0

    # print(f"the type is: {str(type)}")
    try:
        with open(pathfile) as xml_file:
            data_dict = xmltodict.parse(xml_file.read())

            # generate the object using json.dumps()
            # corresponding to json data

            json_data = json.dumps(data_dict)

            # Write the json data to output
            # json file

            d = json.loads(json_data)
            mod = mod.replace(".xml", "")

            if report_tool == "checkov":
                output, fails, tests, message = scan_checkov_reports(
                    data=d, mod=mod, report_tool=report_tool
                )

            elif report_tool == "tfsec":
                # print(d['testsuite'])
                output, fails, tests, message = scan_tfsec_reports(
                    data=d, mod=mod, report_tool=report_tool
                )

            elif report_tool == "terraform-compliance":
                output, fails, tests, message = scan_terraform_compliance_reports(
                    data=d, mod=mod, report_tool=report_tool
                )

            elif report_tool == "terratest":
                output, fails, tests, message = terratest_scan_reports(
                    data=d, mod=mod, report_tool=report_tool
                )
    except Exception as err:
        print(f"It isn't process file {pathfile}")
        output = f"It isn't process file {pathfile}"
        print(err)

    return (
        output,
        fails,
        tests,
        message,
        pathfile,
    )


def message_card(webhook, message="", fails=0, tests=0, in_pipe=False):
    """
    Create message card to format message and sent to Microsoft Teams.

    :param in_pipe: Indicate if the tool is running in a pipeline
    :param webhook:
    :param message:
    :param fails:
    :param tests:
    :return:
    """
    testing_message_summary = pymsteams.connectorcard(webhook)
    testing_message_summary.title("The Terraform Compliance Report was generated")

    testing_message_summary.color("7b9683")
    testing_message_summary.summary("A report was generated")

    # create the section tests
    c_tests = pymsteams.cardsection()
    # Section Title
    c_tests.title("Tests")
    c_tests.text(tests)
    c_tests.activityText("Number of Rules")
    # create the section result
    c_fails = pymsteams.cardsection()
    # Section Title
    c_fails.title("Fails")
    c_fails.text(fails)
    c_fails.activityText("Number of Non Compliance!")
    # create the section result
    result = pymsteams.cardsection()
    # Section Title
    result.title("Result")
    result.text(message)

    testing_message_summary.addSection(c_tests)
    testing_message_summary.addSection(c_fails)
    testing_message_summary.addSection(result)

    result.activityText(f"Non Compliance {fails} of {tests}!")
    if "Approve" in message:
        result.activityImage(
            "https://support.content.office.net/en-us/media/773afccb-4687-4b9f-8a89-8b32f640b27d.png"
        )
    elif "Skipping" in message:
        result.activityImage(
            "https://support.content.office.net/en-us/media/47588200-0bf0-46e9-977e-e668978f459c.png"
        )
    else:
        result.activityImage(
            "https://support.content.office.net/en-us/media/6b8c0bff-7ddc-4bff-9101-8360f8c8a727.png"
        )

    if in_pipe:
        region = os.environ["AWS_REGION"]

        testing_message_summary.addLinkButton(
            "Watch findings in reports console!",
            f"https://{region}.console.aws.amazon.com/codesuite/codebuild/testReports/reportGroups?region={region}",
        )

    # send the message
    testing_message_summary.send()
    # file.close()


def check_reports(directory, report_tool, webhook: str = ""):
    """
    Check reports and send message to Microsoft Teams.

    :param directory:
    :param report_tool:
    :param webhook:
    :return:
    """
    contents = os.listdir(directory)
    json_summary = {"Summary": []}
    for c in contents:
        if c.endswith("xml"):
            # print(mod)
            print(Fore.GREEN + f"Reading Report {c}" + Fore.RESET)

            filename = f"{os.path.join(directory, c)}"

            summary = scan_reports(report_tool=report_tool, pathfile=filename, mod=c)

            message = summary[0]
            fails = summary[1]
            tests = summary[2]
            clean_message = summary[3]

            if fails > 0 and tests > 0:
                json_summary["Summary"].append(
                    {
                        "Name": c,
                        "summary": clean_message,
                        "fails": fails,
                        "tests": tests,
                    }
                )
                # Send message to teams
                if len(webhook) > 0:
                    time.sleep(1)
                    message_card(webhook, message=message, fails=fails, tests=tests)

    logging.info(json.dumps(json_summary, indent=4))
    create_report(json_summary, directory)


def create_report(report, reports_dir):
    """
    Create html report with custom style.

    :param reports_dir:
    :param report:
    :param create_zip_files
    :return:
    """
    current_date = datetime.datetime.today()
    # initializing variables with values
    formatted_date = current_date.strftime("%Y%m%d_%H%M%S")
    file_name = f"SummaryComplianceFindings_{formatted_date}"
    logging.info(" Creating reports ...")
    body = """
        <html>
        <style>
      .tbl { border-collapse: collapse; width:300px; }
      .tbl th, .tbl td { padding: 5px; border: solid 1px #777; }
      .tbl th { background-color: #00ff0080; }
      .tbl-separate { border-collapse: separate; border-spacing: 5px;}

          .fl-table {
            border-radius: 5px;
            font-size: 12px;
            font-weight: normal;
            border: none;
            border-collapse: collapse;
            width: 100%;
            max-width: 100%;
            white-space: nowrap;
            background-color: white;

        }

        .fl-table td, .fl-table th {
            text-align: left;
            padding: 8px;
            border: solid 1px #777;
        }

        .fl-table td {
            border-right: 1px solid #f8f8f8;
            font-size: 14px;
        }

        .fl-table thead th {
            color: #ffffff;
            background: #35259C;
        }


        .fl-table thead th:nth-child(odd) {
            color: #ffffff;
            background: #324960;
        }

        .fl-table tr:nth-child(even) {
            background: #F8F8F8;
        }

        </style>

          <h1 style="font-size:100px; color:black; margin:10px;">Compliance Findings for IaC </h1>

        <p style="font-size:30px; color: black;"><em>Compliance Findings for IaC using IaC peerbot</em></p>

          </html>
        """
    report_path = os.path.join(reports_dir, f"{file_name}.html")
    with open(report_path, "w") as file:
        file.write(body)
        logging.info("Creating HTML Report...")
        content = json2html.convert(
            json=report, table_attributes='id="report-table" class="fl-table"'
        )
        print(content, file=file)
    # Create pdf file
    options = {
        "page-size": "A0",
        "margin-top": "0.7in",
        "margin-right": "0.7in",
        "margin-bottom": "0.7in",
        "margin-left": "0.7in",
        "encoding": "UTF-8",
        "orientation": "Landscape",
    }
    logging.info("Creating PDF Report...")
    pdfkit.from_file(
        f"{reports_dir}/{file_name}.html",
        f"{reports_dir}/{file_name}.pdf",
        options=options,
    )
    files_paths = [f"{reports_dir}/{file_name}.html", f"{reports_dir}/{file_name}.pdf"]

    return files_paths
