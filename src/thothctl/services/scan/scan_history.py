"""Scan history — SQLite-based local storage for scan trend tracking."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DB_PATH = Path.home() / ".thothcf" / "scan_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    directory TEXT NOT NULL,
    total_findings INTEGER DEFAULT 0,
    total_passed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scan_tool_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES scan_runs(id),
    tool TEXT NOT NULL,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    warnings INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scan_severity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES scan_runs(id),
    severity TEXT NOT NULL,
    count INTEGER DEFAULT 0
);
"""


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_SCHEMA)
    return conn


def save_scan(directory: str, results: dict) -> int:
    """Save scan results to history. Returns the run_id."""
    conn = _get_conn()
    try:
        total_passed = total_failed = 0
        total_findings = results.get("summary", {}).get("total_issues", 0)

        # Insert run
        cur = conn.execute(
            "INSERT INTO scan_runs (timestamp, directory, total_findings, total_passed, total_failed) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), os.path.abspath(directory), total_findings, 0, 0),
        )
        run_id = cur.lastrowid

        # Insert per-tool results + severity
        for tool_name, tool_data in results.items():
            if tool_name == "summary" or not isinstance(tool_data, dict):
                continue
            rd = tool_data.get("report_data", {})
            passed = rd.get("passed_count", 0)
            failed = rd.get("failed_count", 0)
            skipped = rd.get("skipped_count", 0)
            warnings = rd.get("warning_count", 0)
            errors = rd.get("error_count", 0)
            total_passed += passed
            total_failed += failed + errors

            conn.execute(
                "INSERT INTO scan_tool_results (run_id, tool, passed, failed, skipped, warnings, errors) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, tool_name, passed, failed, skipped, warnings, errors),
            )

            # Severity from findings
            sev_counts: Dict[str, int] = {}
            for f in tool_data.get("findings", []):
                sev = f.get("severity", "MEDIUM")
                sev_counts[sev] = sev_counts.get(sev, 0) + 1
            for sev, count in sev_counts.items():
                conn.execute(
                    "INSERT INTO scan_severity (run_id, severity, count) VALUES (?, ?, ?)",
                    (run_id, sev, count),
                )

        # Update totals
        conn.execute(
            "UPDATE scan_runs SET total_passed = ?, total_failed = ? WHERE id = ?",
            (total_passed, total_failed, run_id),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def get_previous_run(directory: str) -> Optional[dict]:
    """Get the most recent previous scan for a directory."""
    conn = _get_conn()
    try:
        abs_dir = os.path.abspath(directory)
        # Get last 2 runs (current might already be saved, so we compare with the one before)
        rows = conn.execute(
            "SELECT id, timestamp, total_findings, total_passed, total_failed FROM scan_runs WHERE directory = ? ORDER BY timestamp DESC LIMIT 1",
            (abs_dir,),
        ).fetchall()

        if not rows:
            return None

        run_id, ts, findings, passed, failed = rows[0]

        # Get tool breakdown
        tools = {}
        for row in conn.execute(
            "SELECT tool, passed, failed, skipped, warnings, errors FROM scan_tool_results WHERE run_id = ?",
            (run_id,),
        ):
            tools[row[0]] = {"passed": row[1], "failed": row[2], "skipped": row[3], "warnings": row[4], "errors": row[5]}

        # Get severity
        severity = {}
        for row in conn.execute(
            "SELECT severity, count FROM scan_severity WHERE run_id = ?",
            (run_id,),
        ):
            severity[row[0]] = row[1]

        return {
            "timestamp": ts,
            "total_findings": findings,
            "total_passed": passed,
            "total_failed": failed,
            "tools": tools,
            "severity_counts": severity,
        }
    finally:
        conn.close()


def build_trend(previous: dict, current_results: dict) -> List[dict]:
    """Build trend comparison rows between previous and current scan."""
    rows = []

    # Total findings
    curr_findings = current_results.get("summary", {}).get("total_issues", 0)
    prev_findings = previous.get("total_findings", 0)
    rows.append(_trend_row("Findings", prev_findings, curr_findings, lower_is_better=True))

    # Total passed/failed
    curr_passed = curr_failed = 0
    for tool_name, td in current_results.items():
        if tool_name == "summary" or not isinstance(td, dict):
            continue
        rd = td.get("report_data", {})
        curr_passed += rd.get("passed_count", 0)
        curr_failed += rd.get("failed_count", 0) + rd.get("error_count", 0)

    rows.append(_trend_row("Passed", previous.get("total_passed", 0), curr_passed, lower_is_better=False))
    rows.append(_trend_row("Failed", previous.get("total_failed", 0), curr_failed, lower_is_better=True))

    # Severity
    curr_sev: Dict[str, int] = {}
    for tool_name, td in current_results.items():
        if tool_name == "summary" or not isinstance(td, dict):
            continue
        for f in td.get("findings", []):
            sev = f.get("severity", "MEDIUM")
            curr_sev[sev] = curr_sev.get(sev, 0) + 1

    prev_sev = previous.get("severity_counts", {})
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        p = prev_sev.get(sev, 0)
        c = curr_sev.get(sev, 0)
        if p > 0 or c > 0:
            rows.append(_trend_row(sev, p, c, lower_is_better=True))

    return rows


def _trend_row(metric: str, previous: int, current: int, lower_is_better: bool) -> dict:
    delta = current - previous
    if delta == 0:
        symbol = "→"
        status = "neutral"
    elif (delta < 0 and lower_is_better) or (delta > 0 and not lower_is_better):
        symbol = "↓" if delta < 0 else "↑"
        status = "improved"
    else:
        symbol = "↑" if delta > 0 else "↓"
        status = "regressed"

    return {
        "metric": metric,
        "previous": previous,
        "current": current,
        "delta": delta,
        "symbol": symbol,
        "status": status,
    }
