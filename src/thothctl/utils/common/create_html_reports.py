"""Create HTML reports from XML files."""
import os
import glob
import logging
from pathlib import Path
from typing import List, Optional, Dict
import datetime
import xml.etree.ElementTree as ET

import junitparser
from jinja2 import Environment, FileSystemLoader


class HTMLReportGenerator:
    """Generate HTML reports from XML files."""

    def __init__(self):
        """Initialize the HTML report generator."""
        self.logger = logging.getLogger(__name__)
        self.template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

    def create_html_reports(self, directory: str, mode: str = "simple"):
        """Create HTML reports from XML files."""
        self.logger.info(f"Converting Reports using {mode} mode...")
        self.logger.info(f"Scanning for XML files in directory: {directory}")
        
        # Use absolute path
        abs_directory = os.path.abspath(directory)
        self.logger.info(f"Absolute directory path: {abs_directory}")
        
        # Search for XML files recursively - look for both naming patterns
        xml_files = []
        
        # First look for files with the pattern results_junitxml.xml (Checkov's actual output pattern)
        for root, _, files in os.walk(abs_directory):
            for file in files:
                if file == "results_junitxml.xml":
                    xml_path = os.path.join(root, file)
                    self.logger.info(f"Found XML file: {xml_path}")
                    xml_files.append(xml_path)
                elif file.endswith("_results_junitxml.xml"):  # Also check for the old expected pattern
                    xml_path = os.path.join(root, file)
                    self.logger.info(f"Found XML file with old pattern: {xml_path}")
                    xml_files.append(xml_path)
                elif file.endswith(".xml"):  # Check any other XML files as a fallback
                    xml_path = os.path.join(root, file)
                    self.logger.info(f"Found potential XML file: {xml_path}")
                    # Check if it's a valid JUnit XML file
                    try:
                        junitparser.JUnitXml.fromfile(xml_path)
                        self.logger.info(f"Valid JUnit XML file: {xml_path}")
                        xml_files.append(xml_path)
                    except Exception as e:
                        self.logger.warning(f"Not a valid JUnit XML file: {xml_path} - {e}")
        
        if not xml_files:
            self.logger.warning(f"No XML files found in {abs_directory} or its subdirectories")
            print("No XML files found!")
            
            # Try to find any XML files that might have been created
            all_xml_files = glob.glob(f"{abs_directory}/**/*.xml", recursive=True)
            if all_xml_files:
                self.logger.info(f"Found {len(all_xml_files)} XML files in directory (not JUnit format):")
                for xml_file in all_xml_files:
                    self.logger.info(f"  {xml_file} ({os.path.getsize(xml_file)} bytes)")
            
            # Check if there are any JSON files that might have been created
            json_files = glob.glob(f"{abs_directory}/**/*results_json.json", recursive=True)
            if json_files:
                self.logger.info(f"Found {len(json_files)} JSON result files:")
                for json_file in json_files:
                    self.logger.info(f"  {json_file} ({os.path.getsize(json_file)} bytes)")
            
            return
        
        self.logger.info(f"Found {len(xml_files)} XML files to process")
        
        # Create a reports directory for individual reports
        reports_dir = os.path.join(abs_directory, "html_reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Create individual reports for each XML file
        individual_reports = self.create_individual_reports(xml_files, reports_dir)
        
        # Create an index page that links to all individual reports
        self.create_index_page(individual_reports, reports_dir)
        
        # Also create the simple or xunit report for backward compatibility
        if mode == "simple":
            self._create_simple_report(xml_files, abs_directory)
        else:
            self._create_xunit_report(xml_files, abs_directory)

    def create_individual_reports(self, xml_files: List[str], output_dir: str) -> List[Dict]:
        """Create individual HTML reports for each XML file."""
        individual_reports = []
        
        for xml_file in xml_files:
            try:
                # Get the report name from the directory path
                dir_name = os.path.basename(os.path.dirname(xml_file))
                if dir_name.startswith("report_"):
                    file_name = dir_name
                else:
                    file_name = os.path.basename(xml_file).replace("_results_junitxml.xml", "")
                
                # Create a sanitized filename for the HTML report
                safe_name = "".join(c if c.isalnum() else "_" for c in file_name)
                report_file = f"report_{safe_name}.html"
                report_path = os.path.join(output_dir, report_file)
                
                # Use ElementTree to directly parse the XML file
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Extract test counts from the testsuite element
                total_tests = 0
                total_failures = 0
                total_errors = 0
                total_skipped = 0
                
                for testsuite in root.findall('.//testsuite'):
                    tests = int(testsuite.get('tests', '0'))
                    failures = int(testsuite.get('failures', '0'))
                    errors = int(testsuite.get('errors', '0'))
                    skipped = int(testsuite.get('skipped', '0'))
                    
                    total_tests += tests
                    total_failures += failures
                    total_errors += errors
                    total_skipped += skipped
                
                # Find all testcase elements
                suites = []
                failed_checks = []
                
                # Group testcases by testsuite
                for testsuite in root.findall('.//testsuite'):
                    suite_name = testsuite.get('name', 'Unknown Suite')
                    suite_tests = int(testsuite.get('tests', '0'))
                    suite_failures = int(testsuite.get('failures', '0'))
                    suite_errors = int(testsuite.get('errors', '0'))
                    suite_skipped = int(testsuite.get('skipped', '0'))
                    suite_time = float(testsuite.get('time', '0'))
                    
                    cases = []
                    
                    # Process each testcase in this suite
                    for testcase in testsuite.findall('.//testcase'):
                        name = testcase.get('name', '')
                        classname = testcase.get('classname', '')
                        file_path = testcase.get('file', '')
                        time_str = testcase.get('time', '0')
                        time_value = float(time_str) if time_str else 0.0
                        
                        # Extract check ID and description from the name
                        check_id = ""
                        check_description = ""
                        if name:
                            check_parts = name.split("]", 1)
                            if len(check_parts) > 0:
                                check_id = check_parts[0].replace("[NONE][", "")
                            if len(check_parts) > 1:
                                check_description = check_parts[1].strip()
                        
                        # Check if this testcase has a failure
                        failure = testcase.find('failure')
                        result = "passed"
                        message = ""
                        failure_details = {
                            "resource": "",
                            "file": "",
                            "guideline": ""
                        }
                        
                        if failure is not None:
                            result = "failed"
                            message = failure.get('message', '')
                            failure_text = failure.text.strip() if failure.text else ""
                            
                            # Log the raw failure text for debugging
                            self.logger.info(f"Raw failure text: {failure_text}")
                            
                            # Extract resource, file, and guideline from the failure text
                            failure_lines = failure_text.split('\n')
                            for line in failure_lines:
                                line = line.strip()
                                if line.startswith("Resource:"):
                                    failure_details["resource"] = line.replace("Resource:", "").strip()
                                elif line.startswith("File:"):
                                    failure_details["file"] = line.replace("File:", "").strip()
                                elif line.startswith("Guideline:"):
                                    failure_details["guideline"] = line.replace("Guideline:", "").strip()
                            
                            # If we couldn't extract the details using the above method,
                            # try a different approach
                            if not failure_details["resource"] and len(failure_lines) > 0:
                                failure_details["resource"] = failure_lines[0]
                            if not failure_details["file"] and len(failure_lines) > 1:
                                failure_details["file"] = failure_lines[1]
                            if not failure_details["guideline"] and len(failure_lines) > 2:
                                failure_details["guideline"] = failure_lines[2]
                        
                        case_data = {
                            "name": name,
                            "classname": classname,
                            "file": file_path,
                            "result": result,
                            "message": message,
                            "time": time_value,
                            "check_id": check_id,
                            "check_description": check_description,
                            "failure_details": failure_details
                        }
                        
                        cases.append(case_data)
                        
                        # Add to failed checks list if it's a failure
                        if result == "failed":
                            failed_checks.append(case_data)
                    
                    # Add the suite to the list of suites
                    suites.append({
                        "name": suite_name,
                        "tests": suite_tests,
                        "failures": suite_failures,
                        "errors": suite_errors,
                        "skipped": suite_skipped,
                        "time": suite_time,
                        "cases": cases
                    })
                
                # Debug logging for failed checks
                self.logger.info(f"Found {len(failed_checks)} failed checks in {xml_file}")
                for i, check in enumerate(failed_checks):
                    self.logger.info(f"Failed check {i+1}: {check['check_id']} - {check['check_description']}")
                    self.logger.info(f"  Resource: {check['failure_details']['resource']}")
                    self.logger.info(f"  File: {check['failure_details']['file']}")
                    self.logger.info(f"  Guideline: {check['failure_details']['guideline']}")
                
                # Generate the HTML report
                template = self.env.get_template("individual_report.html")
                
                # Render the template
                html = template.render(
                    report_name=file_name,
                    suites=suites,
                    total_tests=total_tests,
                    total_failures=total_failures,
                    total_errors=total_errors,
                    total_skipped=total_skipped,
                    total_passed=total_tests - total_failures - total_errors - total_skipped,
                    xml_file=xml_file,
                    failed_checks=failed_checks
                )
                
                # Write the HTML file
                with open(report_path, "w") as f:
                    f.write(html)
                
                individual_reports.append({
                    "name": file_name,
                    "path": report_file,
                    "total_tests": total_tests,
                    "failures": total_failures,
                    "errors": total_errors,
                    "skipped": total_skipped,
                    "passed": total_tests - total_failures - total_errors - total_skipped
                })
                
                self.logger.info(f"Created individual report: {report_path}")
                
            except Exception as e:
                self.logger.error(f"Error creating individual report for {xml_file}: {e}", exc_info=True)
        
        return individual_reports

    def create_index_page(self, individual_reports: List[Dict], output_dir: str):
        """Create an index page that links to all individual reports."""
        try:
            template = self.env.get_template("index_report.html")
            
            # Render the template
            html = template.render(reports=individual_reports)
            
            # Write the HTML file - create only one index file in the output directory
            index_path = os.path.join(output_dir, "index.html")
            with open(index_path, "w") as f:
                f.write(html)
            
            self.logger.info(f"Created index page: {index_path}")
            print(f"Created index page: {index_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating index page: {e}")
            print(f"Error creating index page: {e}")

    def _create_simple_report(self, xml_files: List[str], output_dir: str):
        """Create a simple HTML report."""
        try:
            template = self.env.get_template("simple_report.html")
            
            # Parse XML files
            results = []
            for xml_file in xml_files:
                try:
                    # Use ElementTree to directly parse the XML file
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Extract test counts from the testsuite element
                    total = 0
                    failures = 0
                    errors = 0
                    skipped = 0
                    
                    for testsuite in root.findall('.//testsuite'):
                        tests = int(testsuite.get('tests', '0'))
                        failures += int(testsuite.get('failures', '0'))
                        errors += int(testsuite.get('errors', '0'))
                        skipped += int(testsuite.get('skipped', '0'))
                        total += tests
                    
                    # Get file name without path and extension
                    # Extract the report name from the directory path
                    dir_name = os.path.basename(os.path.dirname(xml_file))
                    if dir_name.startswith("report_"):
                        file_name = dir_name
                    else:
                        file_name = os.path.basename(xml_file).replace("_results_junitxml.xml", "")
                    
                    results.append({
                        "name": file_name,
                        "total": total,
                        "failures": failures,
                        "errors": errors,
                        "skipped": skipped,
                        "passed": total - failures - errors - skipped,
                        "file": xml_file
                    })
                except Exception as e:
                    self.logger.error(f"Error parsing XML file {xml_file}: {e}")
            
            # Render template
            html = template.render(results=results)
            
            # Write HTML file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"report_{timestamp}.html")
            with open(output_file, "w") as f:
                f.write(html)
            
            # Also create a copy with a standard name for easy access
            standard_output_file = os.path.join(output_dir, "report.html")
            with open(standard_output_file, "w") as f:
                f.write(html)
            
            self.logger.info(f"Created simple HTML report: {output_file}")
            print(f"Created simple HTML report: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error creating simple HTML report: {e}")
            print(f"Error creating simple HTML report: {e}")

    def _create_xunit_report(self, xml_files: List[str], output_dir: str):
        """Create an xUnit HTML report."""
        try:
            template = self.env.get_template("xunit_report.html")
            
            # Parse XML files
            results = []
            for xml_file in xml_files:
                try:
                    # Use ElementTree to directly parse the XML file
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Find all testcase elements
                    suites = []
                    
                    # Group testcases by testsuite
                    for testsuite in root.findall('.//testsuite'):
                        suite_name = testsuite.get('name', 'Unknown Suite')
                        suite_tests = int(testsuite.get('tests', '0'))
                        suite_failures = int(testsuite.get('failures', '0'))
                        suite_errors = int(testsuite.get('errors', '0'))
                        suite_skipped = int(testsuite.get('skipped', '0'))
                        suite_time = float(testsuite.get('time', '0'))
                        
                        cases = []
                        
                        # Process each testcase in this suite
                        for testcase in testsuite.findall('.//testcase'):
                            name = testcase.get('name', '')
                            classname = testcase.get('classname', '')
                            file_path = testcase.get('file', '')
                            time_str = testcase.get('time', '0')
                            time_value = float(time_str) if time_str else 0.0
                            
                            # Extract check ID and description from the name
                            check_id = ""
                            check_description = ""
                            if name:
                                check_parts = name.split("]", 1)
                                if len(check_parts) > 0:
                                    check_id = check_parts[0].replace("[NONE][", "")
                                if len(check_parts) > 1:
                                    check_description = check_parts[1].strip()
                            
                            # Check if this testcase has a failure
                            failure = testcase.find('failure')
                            result = "passed"
                            message = ""
                            failure_details = {
                                "resource": "",
                                "file": "",
                                "guideline": ""
                            }
                            
                            if failure is not None:
                                result = "failed"
                                message = failure.get('message', '')
                                failure_text = failure.text.strip() if failure.text else ""
                                
                                # Extract resource, file, and guideline from the failure text
                                failure_lines = failure_text.split('\n')
                                for line in failure_lines:
                                    line = line.strip()
                                    if line.startswith("Resource:"):
                                        failure_details["resource"] = line.replace("Resource:", "").strip()
                                    elif line.startswith("File:"):
                                        failure_details["file"] = line.replace("File:", "").strip()
                                    elif line.startswith("Guideline:"):
                                        failure_details["guideline"] = line.replace("Guideline:", "").strip()
                                
                                # If we couldn't extract the details using the above method,
                                # try a different approach
                                if not failure_details["resource"] and len(failure_lines) > 0:
                                    failure_details["resource"] = failure_lines[0]
                                if not failure_details["file"] and len(failure_lines) > 1:
                                    failure_details["file"] = failure_lines[1]
                                if not failure_details["guideline"] and len(failure_lines) > 2:
                                    failure_details["guideline"] = failure_lines[2]
                            
                            cases.append({
                                "name": name,
                                "classname": classname,
                                "file": file_path,
                                "result": result,
                                "message": message,
                                "time": time_value,
                                "check_id": check_id,
                                "check_description": check_description,
                                "failure_details": failure_details
                            })
                        
                        # Add the suite to the list of suites
                        suites.append({
                            "name": suite_name,
                            "tests": suite_tests,
                            "failures": suite_failures,
                            "errors": suite_errors,
                            "skipped": suite_skipped,
                            "time": suite_time,
                            "cases": cases
                        })
                    
                    # Get file name without path and extension
                    # Extract the report name from the directory path
                    dir_name = os.path.basename(os.path.dirname(xml_file))
                    if dir_name.startswith("report_"):
                        file_name = dir_name
                    else:
                        file_name = os.path.basename(xml_file).replace("_results_junitxml.xml", "")
                    
                    results.append({
                        "name": file_name,
                        "suites": suites,
                        "file": xml_file
                    })
                except Exception as e:
                    self.logger.error(f"Error parsing XML file {xml_file}: {e}")
            
            # Render template
            html = template.render(results=results)
            
            # Write HTML file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"report_xunit_{timestamp}.html")
            with open(output_file, "w") as f:
                f.write(html)
            
            # Also create a copy with a standard name for easy access
            standard_output_file = os.path.join(output_dir, "report_xunit.html")
            with open(standard_output_file, "w") as f:
                f.write(html)
            
            self.logger.info(f"Created xUnit HTML report: {output_file}")
            print(f"Created xUnit HTML report: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error creating xUnit HTML report: {e}")
            print(f"Error creating xUnit HTML report: {e}")
