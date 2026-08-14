"""Generation history — SQLite-based local storage for intent-to-IaC runs.

Records every `thothctl generate iac` invocation with metadata, results,
and generated file listings. Powers the dashboard Generation tab.

Database: ~/.thothcf/generation_history.db
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path.home() / ".thothcf" / "generation_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_runs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    intent TEXT NOT NULL,
    project_type TEXT NOT NULL DEFAULT 'terraform-terragrunt',
    composition TEXT NOT NULL DEFAULT 'single',
    output_mode TEXT NOT NULL DEFAULT 'project',
    space TEXT DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'ollama',
    model TEXT DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,
    error TEXT DEFAULT '',
    files_count INTEGER DEFAULT 0,
    iterations INTEGER DEFAULT 1,
    context_tokens INTEGER DEFAULT 0,
    generation_tokens INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0.0,
    violations_initial INTEGER DEFAULT 0,
    violations_final INTEGER DEFAULT 0,
    output_dir TEXT DEFAULT '',
    plan_validation TEXT DEFAULT 'disabled'
);

CREATE TABLE IF NOT EXISTS generation_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES generation_runs(id),
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    size_bytes INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS generation_stacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES generation_runs(id),
    name TEXT NOT NULL,
    layer TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    intent TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS generation_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES generation_runs(id),
    check_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    resource TEXT DEFAULT '',
    message TEXT NOT NULL,
    tool TEXT NOT NULL DEFAULT 'checkov',
    iteration INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON generation_runs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_runs_success ON generation_runs(success);
CREATE INDEX IF NOT EXISTS idx_files_run ON generation_files(run_id);
CREATE INDEX IF NOT EXISTS idx_stacks_run ON generation_stacks(run_id);
CREATE INDEX IF NOT EXISTS idx_violations_run ON generation_violations(run_id);
"""


def _get_conn() -> sqlite3.Connection:
    """Get SQLite connection with schema initialized."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_generation_run(
    intent: str,
    result: Any,
    duration_seconds: float = 0.0,
    project_type: str = "terraform-terragrunt",
    composition: str = "single",
    output_mode: str = "project",
    space: str = "",
    provider: str = "ollama",
    model: str = "",
    output_dir: str = "",
    plan_validation: str = "disabled",
) -> str:
    """Save a generation run to history. Returns the run_id.

    Args:
        intent: The natural language intent.
        result: IntentResult object from the generation pipeline.
        duration_seconds: Total execution time.
        project_type: Target project type.
        composition: Composition mode used.
        output_mode: blueprint or project.
        space: Space name used.
        provider: AI provider.
        model: AI model.
        output_dir: Output directory.
        plan_validation: Plan validation mode used.

    Returns:
        UUID string of the saved run.
    """
    run_id = str(uuid.uuid4())
    conn = _get_conn()

    try:
        # Insert run metadata
        conn.execute(
            """INSERT INTO generation_runs 
            (id, timestamp, intent, project_type, composition, output_mode, 
             space, provider, model, success, error, files_count, iterations,
             context_tokens, generation_tokens, duration_seconds,
             violations_initial, violations_final, output_dir, plan_validation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                datetime.now().isoformat(),
                intent,
                project_type,
                composition,
                output_mode,
                space or "",
                provider,
                model or "",
                1 if result.success else 0,
                result.error or "",
                len(result.files),
                result.iterations,
                result.context_tokens,
                result.generation_tokens,
                duration_seconds,
                0,  # violations_initial (not tracked separately yet)
                result.validation.total_violations if result.validation else 0,
                output_dir or "",
                plan_validation,
            ),
        )

        # Insert generated files
        for f in result.files:
            conn.execute(
                """INSERT INTO generation_files (run_id, path, content, size_bytes)
                VALUES (?, ?, ?, ?)""",
                (run_id, f.path, f.content, len(f.content.encode("utf-8"))),
            )

        # Insert stacks (from estimated_resources or explanation)
        for stack_name in result.estimated_resources:
            conn.execute(
                """INSERT INTO generation_stacks (run_id, name) VALUES (?, ?)""",
                (run_id, stack_name),
            )

        # Insert final violations
        if result.validation and result.validation.violations:
            for v in result.validation.violations:
                conn.execute(
                    """INSERT INTO generation_violations 
                    (run_id, check_id, severity, resource, message, tool, iteration)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        v.check_id,
                        v.severity,
                        v.resource,
                        v.message,
                        v.tool,
                        result.iterations,
                    ),
                )

        conn.commit()
        return run_id

    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_generation_history(
    limit: int = 50,
    offset: int = 0,
    success_only: bool = False,
) -> Dict[str, Any]:
    """Get generation run history with pagination.

    Returns:
        Dict with 'runs' list, 'total' count, and 'metrics' summary.
    """
    conn = _get_conn()
    try:
        # Count total
        where = "WHERE success = 1" if success_only else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM generation_runs {where}"
        ).fetchone()[0]

        # Fetch runs
        rows = conn.execute(
            f"""SELECT id, timestamp, intent, project_type, composition,
                output_mode, space, provider, model, success, error,
                files_count, iterations, context_tokens, generation_tokens,
                duration_seconds, violations_final, output_dir, plan_validation
            FROM generation_runs {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()

        runs = [dict(row) for row in rows]

        # Compute metrics
        metrics = _compute_metrics(conn)

        return {
            "runs": runs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "metrics": metrics,
        }
    finally:
        conn.close()


def get_generation_result(run_id: str) -> Optional[Dict[str, Any]]:
    """Get full details of a specific generation run.

    Returns:
        Dict with run metadata, files, stacks, and violations. None if not found.
    """
    conn = _get_conn()
    try:
        # Get run
        row = conn.execute(
            "SELECT * FROM generation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None

        run = dict(row)

        # Get files
        files = conn.execute(
            "SELECT path, content, size_bytes FROM generation_files WHERE run_id = ? ORDER BY path",
            (run_id,),
        ).fetchall()
        run["files"] = [dict(f) for f in files]

        # Get stacks
        stacks = conn.execute(
            "SELECT name, layer, domain, intent FROM generation_stacks WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        run["stacks"] = [dict(s) for s in stacks]

        # Get violations
        violations = conn.execute(
            "SELECT check_id, severity, resource, message, tool, iteration FROM generation_violations WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        run["violations"] = [dict(v) for v in violations]

        return run
    finally:
        conn.close()


def _compute_metrics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Compute aggregate metrics from generation history."""
    total = conn.execute("SELECT COUNT(*) FROM generation_runs").fetchone()[0]
    if total == 0:
        return {
            "total_runs": 0,
            "success_rate": 0,
            "avg_duration": 0,
            "avg_iterations": 0,
            "total_tokens": 0,
            "avg_files": 0,
        }

    success = conn.execute(
        "SELECT COUNT(*) FROM generation_runs WHERE success = 1"
    ).fetchone()[0]

    avg_duration = conn.execute(
        "SELECT AVG(duration_seconds) FROM generation_runs WHERE success = 1"
    ).fetchone()[0] or 0

    avg_iterations = conn.execute(
        "SELECT AVG(iterations) FROM generation_runs WHERE success = 1"
    ).fetchone()[0] or 0

    total_tokens = conn.execute(
        "SELECT SUM(context_tokens + generation_tokens) FROM generation_runs"
    ).fetchone()[0] or 0

    avg_files = conn.execute(
        "SELECT AVG(files_count) FROM generation_runs WHERE success = 1"
    ).fetchone()[0] or 0

    # Composition breakdown
    compositions = conn.execute(
        "SELECT composition, COUNT(*) as count FROM generation_runs GROUP BY composition"
    ).fetchall()

    # Provider breakdown
    providers = conn.execute(
        "SELECT provider, COUNT(*) as count FROM generation_runs GROUP BY provider"
    ).fetchall()

    return {
        "total_runs": total,
        "success_rate": round((success / total) * 100, 1) if total else 0,
        "avg_duration": round(avg_duration, 1),
        "avg_iterations": round(avg_iterations, 1),
        "total_tokens": total_tokens,
        "avg_files": round(avg_files, 1),
        "compositions": {row[0]: row[1] for row in compositions},
        "providers": {row[0]: row[1] for row in providers},
    }
