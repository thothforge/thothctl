"""Tests for stack-qualified Checkov finding paths and SARIF result identity.

Regression for the SecObserve under-reporting bug: multi-stack Checkov findings
were all attributed to a generic ``/main.tf`` path, so distinct resources/stacks
sharing a rule collapsed into a single observation.
"""

import json
import os

from thothctl.services.scan.report_parser import _extract_checkov_findings
from thothctl.services.scan.sarif_output import build_sarif


def _checkov_json(scan_root, rel_file, checks):
    """Build a minimal checkov results_json.json payload.

    checks: list of (check_id, resource, line)
    """
    failed = []
    for check_id, resource, line in checks:
        failed.append(
            {
                "check_id": check_id,
                "check_name": f"{check_id} name",
                "resource": resource,
                "severity": "HIGH",
                "file_path": rel_file,  # relative to the scanned stack (e.g. /main.tf)
                "file_abs_path": f"{scan_root}{rel_file}",
                "repo_file_path": f"{scan_root}{rel_file}",
                "file_line_range": [line, line + 1],
            }
        )
    return {"results": {"failed_checks": failed}}


def _write_stack_report(checkov_dir, report_name, payload):
    d = os.path.join(checkov_dir, report_name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "results_json.json"), "w") as f:
        json.dump(payload, f)


def _make_multistack_reports(tmp_path):
    """Two stacks, each with the same two rules on the same resource/line."""
    scan_root = str(tmp_path / "repo")
    checkov_dir = str(tmp_path / "Reports" / "checkov" / "security-scan")
    os.makedirs(checkov_dir)
    for stack in ("network", "data"):
        _write_stack_report(
            checkov_dir,
            f"report_stacks_{stack}",
            _checkov_json(
                f"{scan_root}/stacks/{stack}",
                "/main.tf",
                [("CKV_AWS_286", "aws_security_group.sg", 3),
                 ("CKV_AWS_23", "aws_security_group.sg", 3)],
            ),
        )
    return checkov_dir


class TestStackQualifiedPaths:
    def test_paths_are_distinct_per_stack(self, tmp_path):
        checkov_dir = _make_multistack_reports(tmp_path)
        findings = _extract_checkov_findings(checkov_dir)
        assert len(findings) == 4  # 2 rules x 2 stacks
        files = {f.file for f in findings}
        assert files == {"stacks/network/main.tf", "stacks/data/main.tf"}
        # No finding keeps the generic path.
        assert all(f.file != "/main.tf" for f in findings)

    def test_falls_back_to_report_dir_hint_without_abs_path(self, tmp_path):
        checkov_dir = str(tmp_path / "Reports" / "checkov" / "security-scan")
        os.makedirs(checkov_dir)
        payload = {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_1",
                        "check_name": "n",
                        "resource": "aws_s3_bucket.b",
                        "severity": "HIGH",
                        "file_path": "/main.tf",  # no abs path available
                        "file_line_range": [1, 2],
                    }
                ]
            }
        }
        _write_stack_report(checkov_dir, "report_stacks_network", payload)
        findings = _extract_checkov_findings(checkov_dir)
        assert findings[0].file == "stacks/network/main.tf"

    def test_single_dir_root_report_keeps_relative_path(self, tmp_path):
        checkov_dir = str(tmp_path / "Reports" / "checkov" / "security-scan")
        scan_root = str(tmp_path / "proj")
        os.makedirs(checkov_dir)
        # "report_<parent>_<name>" of the scanned dir -> stack hint "tmp/proj"
        _write_stack_report(
            checkov_dir,
            "report_tmp_proj",
            _checkov_json(scan_root, "/modules/vpc/main.tf", [("CKV_AWS_1", "r", 5)]),
        )
        findings = _extract_checkov_findings(checkov_dir)
        # stack hint + in-stack path (no generic/collapsed path)
        assert findings[0].file == "tmp/proj/modules/vpc/main.tf"


class TestSarifResultIdentity:
    def test_same_rule_different_stacks_not_collapsed(self, tmp_path):
        checkov_dir = _make_multistack_reports(tmp_path)
        findings = _extract_checkov_findings(checkov_dir)
        doc = build_sarif(
            {"checkov": {"status": "COMPLETE", "findings": [f.__dict__ for f in findings]}},
            str(tmp_path),
        )
        results = doc["runs"][0]["results"]
        assert len(results) == 4
        # Physical locations differ by stack path.
        uris = {
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for r in results
        }
        assert uris == {"stacks/network/main.tf", "stacks/data/main.tf"}
        # Every result has a unique fingerprint (no collapse).
        fps = {r["partialFingerprints"]["thothctl/v1"] for r in results}
        assert len(fps) == 4

    def test_fingerprint_separates_resources_sharing_file_and_line(self, tmp_path):
        findings = [
            {"id": "CKV_AWS_1", "severity": "HIGH", "title": "t",
             "file": "stacks/net/main.tf", "line": 10, "resource": "aws_s3_bucket.a"},
            {"id": "CKV_AWS_1", "severity": "HIGH", "title": "t",
             "file": "stacks/net/main.tf", "line": 10, "resource": "aws_s3_bucket.b"},
        ]
        doc = build_sarif({"checkov": {"status": "COMPLETE", "findings": findings}}, ".")
        results = doc["runs"][0]["results"]
        fps = {r["partialFingerprints"]["thothctl/v1"] for r in results}
        assert len(fps) == 2  # same rule+file+line, different resource
        locs = results[0]["locations"][0]
        assert locs["logicalLocations"][0]["name"] == "aws_s3_bucket.a"

    def test_resource_appended_to_message(self, tmp_path):
        findings = [
            {"id": "CKV_AWS_1", "severity": "HIGH", "title": "Enable encryption",
             "file": "main.tf", "line": 1, "resource": "aws_s3_bucket.b"},
        ]
        doc = build_sarif({"checkov": {"status": "COMPLETE", "findings": findings}}, ".")
        msg = doc["runs"][0]["results"][0]["message"]["text"]
        assert "aws_s3_bucket.b" in msg
