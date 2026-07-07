"""
Evidence Store: persists functional agent (and future agents') test results
so they can be queried across a run and across time, instead of living only
in throwaway JSON files. SQLite chosen deliberately - zero infra cost, zero
setup, sufficient for single-machine testing runs at this stage. Can swap
for Postgres later without changing the calling code much.
"""
import sqlite3
import json
import uuid
import datetime
import os

DB_PATH = os.path.join("db", "evidence.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            target_url TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            agent_type TEXT,
            todo_type TEXT,
            url TEXT,
            auth_state TEXT,
            form_type TEXT,
            button_type TEXT,
            case_name TEXT,
            expect TEXT,
            outcome TEXT,
            result_type TEXT,
            likely_error_shown INTEGER,
            screenshot TEXT,
            severity TEXT,
            note TEXT,
            raw_json TEXT,
            created_at TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)
    conn.commit()
    conn.close()


def start_run(target_url: str) -> str:
    """Call once at the beginning of a full pipeline run. Returns run_id."""
    init_db()
    run_id = str(uuid.uuid4())
    conn = _connect()
    conn.execute(
        "INSERT INTO runs (run_id, target_url, started_at, status) VALUES (?, ?, ?, ?)",
        (run_id, target_url, datetime.datetime.utcnow().isoformat(), "in_progress")
    )
    conn.commit()
    conn.close()
    return run_id


def finish_run(run_id: str, status: str = "completed"):
    conn = _connect()
    conn.execute(
        "UPDATE runs SET finished_at = ?, status = ? WHERE run_id = ?",
        (datetime.datetime.utcnow().isoformat(), status, run_id)
    )
    conn.commit()
    conn.close()


def save_evidence(run_id: str, agent_type: str, evidence: list):
    """
    evidence: list of dicts as produced by run_functional_agent() (or any
    future agent following the same loose shape). Stores structured columns
    for common fields plus the full record as raw_json for anything
    agent-specific we haven't promoted to a column yet.
    """
    conn = _connect()
    now = datetime.datetime.utcnow().isoformat()

    for record in evidence:
        conn.execute("""
            INSERT INTO evidence (
                id, run_id, agent_type, todo_type, url, auth_state,
                form_type, button_type, case_name, expect, outcome,
                result_type, likely_error_shown, screenshot, severity,
                note, raw_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), run_id, agent_type,
            record.get("todo_type"),
            record.get("url"),
            record.get("auth_state"),
            record.get("form_type"),
            record.get("button_type"),
            record.get("case_name"),
            record.get("expect"),
            record.get("outcome"),
            record.get("result_type"),
            1 if record.get("likely_error_shown") else 0,
            record.get("screenshot"),
            record.get("severity"),
            record.get("note"),
            json.dumps(record, default=str),
            now,
        ))

    conn.commit()
    conn.close()


def get_run_evidence(run_id: str) -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM evidence WHERE run_id = ?", (run_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_flagged_evidence(run_id: str) -> list:
    """
    Convenience query: things worth a human's attention -
    access control findings, possible missing validation, execution errors.
    """
    conn = _connect()
    rows = conn.execute("""
        SELECT * FROM evidence WHERE run_id = ? AND (
            todo_type = 'access_control_check'
            OR (outcome = 'executed' AND result_type = 'no_visible_change' AND expect = 'validation_error')
            OR outcome = 'execution_failed'
        )
    """, (run_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_runs() -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]